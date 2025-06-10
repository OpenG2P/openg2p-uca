import asyncio
import fractions
import functools
import io
import logging
import uuid
from datetime import datetime, timezone

import av
from aiortc import (
    AudioStreamTrack,
    MediaStreamError,
    MediaStreamTrack,
    RTCConfiguration,
    RTCPeerConnection,
    RTCSessionDescription,
)
from openg2p_fastapi_common.controller import BaseController
from openg2p_llm_common.errors import STTUnsupportedAudioFormat
from openg2p_llm_common.schemas.ollama import OllamaChatMessage, OllamaChatResponse
from openg2p_llm_common.services.agents import BaseAgentSystem
from openg2p_llm_common.services.stt.base import BaseSTTRequest, BaseSTTService
from openg2p_llm_common.services.tts.base import BaseTTSService

from ..config import Settings
from ..schemas.call import UcaCallMetaResponse, UcaCallOfferRequest, UcaCallOfferResponse

_config = Settings.get_config()
_logger = logging.getLogger(_config.logging_default_logger_name)


class UcaQueueAudioTrack(AudioStreamTrack):
    """A custom AudioStreamTrack that plays audio from an asyncio.Queue buffer."""

    def __init__(self):
        super().__init__()
        self.current_pts = 0  # Presentation timestamp for outgoing frames
        self.queue = asyncio.Queue()

    async def recv(self):
        if self.readyState != "live":
            raise MediaStreamError
        frame: av.AudioFrame = await self.queue.get()
        # Ensure PTS and time_base are correctly set for continuous playback
        # This is critical for WebRTC to synchronize audio
        frame.pts = self.current_pts
        frame.time_base = fractions.Fraction(1, frame.sample_rate)
        # Advance the PTS for the next frame
        self.current_pts += frame.samples
        return frame


class UcaCallRTCPeerConnection(RTCPeerConnection):
    def __init__(
        self,
        id: str | None = None,
        messages: list[OllamaChatMessage] | None = None,
        output_audio_track: UcaQueueAudioTrack | None = None,
        configuration: RTCConfiguration | None = None,
        **kw
    ) -> None:
        if configuration and not kw.get("configuration"):
            kw["configuration"] = configuration
        super().__init__(**kw)
        self.id = id or str(uuid.uuid4())
        self.messages = messages
        self.output_audio_track = output_audio_track
        self.input_audio_track: AudioStreamTrack = None

    async def add_output_audio_frames(self, *args: av.AudioFrame):
        for f in args:
            await self.output_audio_track.queue.put(f)

    async def close(self, **kw):
        self.output_audio_track.cancel()
        if self.input_audio_track:
            self.input_audio_track.cancel()
        await super().close(**kw)


class CallController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.rtc_peer_connections: dict[
            str, UcaCallRTCPeerConnection
        ] = {}  # TODO: Move this to better system

        self.agent_system: BaseAgentSystem = None
        self.stt_service: BaseSTTService = None
        self.tts_service: BaseTTSService = None
        self.system_prompt_call_suffix: str = None
        self.call_standby_message_text: str = None
        self.call_standby_message_audio: av.AudioFrame = None
        self.resampler: av.AudioResampler = None

        self.meta_response: UcaCallMetaResponse = None

        self.router.prefix += "/call"
        self.router.tags += ["call"]
        self.router.add_api_route(
            "/meta",
            self.get_call_meta,
            responses={200: {"model": UcaCallMetaResponse}},
            methods=["GET"],
        )
        self.router.add_api_route(
            "/offer",
            self.post_new_call_offer,
            responses={200: {"model": UcaCallOfferResponse}},
            methods=["POST"],
        )

    async def initialize(self):
        self.resampler = av.AudioResampler(
            format="s16", layout="mono", rate=_config.stt_supported_sample_rate
        )

        self.agent_system = BaseAgentSystem.get_component()
        self.stt_service = BaseSTTService.get_component()
        self.tts_service = BaseTTSService.get_component()

        self.meta_response = UcaCallMetaResponse(iceServers=_config.call_meta_ice_servers or [])

        with open(_config.default_system_prompt_suffix_for_call_path) as file:
            self.system_prompt_call_suffix = file.read().strip()

        with open(_config.call_standby_message_path) as file:
            self.call_standby_message_text = file.read().strip()
        self.call_standby_message_audio = self.tts_service.generate_audio_frame_from_raw_audio(
            self.tts_service.convert_text_to_raw_audio(self.call_standby_message_text)
        )

    async def get_call_meta(self):
        return self.meta_response

    async def post_new_call_offer(self, request: UcaCallOfferRequest):
        pc = self.rtc_call_create_new_connection()
        server_audio_track = UcaQueueAudioTrack()
        pc.output_audio_track = server_audio_track
        pc.addTrack(server_audio_track)
        pc.add_listener("track", functools.partial(self.rtc_call_on_track, pc))
        pc.add_listener(
            "connectionstatechange", functools.partial(self.rtc_call_on_connectionstatechange, pc)
        )

        offer = RTCSessionDescription(sdp=request.sdp, type=request.sdp_type)
        await pc.setRemoteDescription(offer)

        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        _logger.info("Call Creation: Sending SDP answer.")
        return UcaCallOfferResponse(type="answer", sdp=pc.localDescription.sdp)

    def rtc_call_create_new_connection(self, **kw) -> UcaCallRTCPeerConnection:
        pc = UcaCallRTCPeerConnection(**kw)
        self.rtc_peer_connections[pc.id] = pc
        return pc

    async def rtc_call_close_connection(self, rtc_conn: UcaCallRTCPeerConnection, **kw):
        if rtc_conn and rtc_conn.connectionState != "closed":
            await rtc_conn.close(**kw)
        _logger.info("Call Termination: RTC peer connection closed.")
        self.rtc_peer_connections.pop(rtc_conn.id)

    async def rtc_call_on_connectionstatechange(self, rtc_conn: UcaCallRTCPeerConnection):
        _logger.info("Call State Change: RTC connection state is %s", rtc_conn.connectionState)
        if rtc_conn.connectionState == "connected":
            self.rtc_call_create_thread(rtc_conn)
        if rtc_conn.connectionState in ["failed", "closed"]:
            try:
                await self.rtc_call_close_connection(rtc_conn)
            except Exception:
                _logger.exception("Call State Change: Unable to close RTC conn. Maybe already closed.")

    async def rtc_call_on_track(self, rtc_conn: UcaCallRTCPeerConnection, track: MediaStreamTrack):
        _logger.info(
            "Call On Track: Track received from remote peer. Id - %s. Kind - %s", track.id, track.kind
        )
        if track.kind == "audio":
            rtc_conn.input_audio_track = track
            stt_request = self.stt_service.create_new_request()
            while True:
                try:
                    await self.rtc_call_process_audio(rtc_conn, track, stt_request)
                except Exception:
                    _logger.exception("Call On Track: Process Audio failed.")
                    break

    async def rtc_call_process_audio(
        self, rtc_conn: UcaCallRTCPeerConnection, track: MediaStreamTrack, stt_request: BaseSTTRequest
    ):
        aframe: av.AudioFrame = await track.recv()
        out_bytes = io.BytesIO()
        try:
            for resampled_frame in self.resampler.resample(aframe):
                out_bytes.write(resampled_frame.to_ndarray().flatten().tobytes())
        except Exception as e:
            err = STTUnsupportedAudioFormat()
            err.message += ". Could not resample input frame."
            raise err from e
        self.stt_service.add_audio_to_request(stt_request, out_bytes.getvalue())
        if not rtc_conn.messages:
            # The call initiation is not finished
            return
        if not self.stt_service.is_silence_detected(stt_request):
            # Silence is not detected so dont proceed further
            return
        text = (
            self.stt_service.convert_request_to_text(stt_request)
            + " "
            + self.stt_service.flush_audio_in_request(stt_request)
        ).strip()
        if not text:
            return
        rtc_conn.messages.append(
            OllamaChatMessage(role="user", content=text, agent_name=rtc_conn.messages[-1].agent_name)
        )
        task = asyncio.create_task(self.llm_chat_speak(rtc_conn))
        timer_task = asyncio.create_task(asyncio.sleep(_config.call_standby_message_timer))

        done_async_tasks, pending_async_tasks = await asyncio.wait(
            [task, timer_task], return_when=asyncio.FIRST_COMPLETED
        )
        if task in pending_async_tasks and timer_task in done_async_tasks:
            # LLM Response taking longer than standby timer.
            # So respond with standby message
            await rtc_conn.add_output_audio_frames(self.call_standby_message_audio)

    def rtc_call_create_thread(
        self, rtc_conn: UcaCallRTCPeerConnection, system_prompt_params: dict | None = None, **kw
    ):
        system_prompt_params = system_prompt_params or {}
        stored_system_prompt = self.system_prompt_call_suffix.format(**system_prompt_params).strip()
        rtc_conn.messages = [OllamaChatMessage(role="system", content=stored_system_prompt)]
        asyncio.create_task(self.llm_chat_speak(rtc_conn, **kw))

    async def llm_chat(
        self, rtc_conn: UcaCallRTCPeerConnection, message_sent_at: datetime | None = None, **kw
    ) -> str:
        message_sent_at = message_sent_at or datetime.now(timezone.utc)
        agent = self.agent_system.get_agent_or_default(rtc_conn.messages[-1].agent_name)
        res = await agent.chat(rtc_conn.messages, message_sent_at=message_sent_at, **kw)
        for msg in res:
            if isinstance(msg, OllamaChatResponse):
                if msg.message.content:
                    rtc_conn.messages.append(msg.message)
            elif isinstance(msg, OllamaChatMessage):
                if msg.content:
                    rtc_conn.messages.append(msg)
        return rtc_conn.messages[-1].content

    async def llm_chat_speak(
        self, rtc_conn: UcaCallRTCPeerConnection, message_sent_at: datetime | None = None, **kw
    ):
        llm_res = await self.llm_chat(rtc_conn, message_sent_at=message_sent_at, **kw)
        tts_res = self.tts_service.convert_text_to_raw_audio(llm_res)
        aframe = self.tts_service.generate_audio_frame_from_raw_audio(tts_res)
        await rtc_conn.add_output_audio_frames(aframe)
