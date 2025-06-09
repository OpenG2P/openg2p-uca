import asyncio
import fractions
import functools
import io
import logging
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
from fastapi import WebSocket, WebSocketDisconnect
from openg2p_fastapi_common.controller import BaseController
from openg2p_llm_common.errors import STTUnsupportedAudioFormat
from openg2p_llm_common.schemas.ollama import OllamaChatMessage, OllamaChatResponse
from openg2p_llm_common.services.agents import BaseAgentSystem
from openg2p_llm_common.services.stt.base import BaseSTTRequest, BaseSTTService
from openg2p_llm_common.services.tts.base import BaseTTSService

from ..config import Settings

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
        websocket: WebSocket | None = None,
        configuration: RTCConfiguration | None = None,
        messages: list[OllamaChatMessage] | None = None,
        output_audio_track: UcaQueueAudioTrack | None = None,
        **kw
    ) -> None:
        if configuration and not kw.get("configuration"):
            kw["configuration"] = configuration
        super().__init__(**kw)
        self.websocket = websocket
        self.messages = messages
        self.output_audio_track = output_audio_track

    def add_output_audio_frames(self, *args: av.AudioFrame):
        for f in args:
            self.output_audio_track.queue.put_nowait(f)


class CallController(BaseController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.agent_system: BaseAgentSystem = None
        self.stt_service: BaseSTTService = None
        self.tts_service: BaseTTSService = None
        self.system_prompt_call_suffix: str = None
        self.call_standby_message_text: str = None
        self.call_standby_message_audio: av.AudioFrame = None
        self.resampler: av.AudioResampler = None

        self.router.tags += ["chat"]
        self.router.add_websocket_route(
            "/call",
            self.websocket_call,
        )

    async def initialize(self):
        self.resampler = av.AudioResampler(
            format="s16", layout="mono", rate=_config.stt_supported_sample_rate
        )

        self.agent_system = BaseAgentSystem.get_component()
        self.stt_service = BaseSTTService.get_component()
        self.tts_service = BaseTTSService.get_component()

        with open(_config.default_system_prompt_suffix_for_call_path) as file:
            self.system_prompt_call_suffix = file.read().strip()

        with open(_config.call_standby_message_path) as file:
            self.call_standby_message_text = file.read().strip()
        self.call_standby_message_audio = self.tts_service.generate_audio_frame_from_raw_audio(
            self.tts_service.convert_text_to_raw_audio(self.call_standby_message_text)
        )

    async def websocket_call(self, websocket: WebSocket):
        await websocket.accept()
        _logger.info("Call WebSocket: Accepted.")

        server_audio_track = UcaQueueAudioTrack()
        pc = UcaCallRTCPeerConnection(
            websocket=websocket,
            output_audio_track=server_audio_track,
        )
        pc.addTrack(server_audio_track)
        pc.add_listener("icecandidate", functools.partial(self.rtc_call_on_icecandidate, pc))
        pc.add_listener("track", functools.partial(self.rtc_call_on_track, pc))

        try:
            while True:
                # This receive_json breaks when the websocket is closed from the client.
                # Which will then result in rtcpeerconnection closure.
                data = await websocket.receive_json()
                if data["type"] == "offer":
                    _logger.info("Call WebSocket: Received SDP offer.")
                    offer = RTCSessionDescription(sdp=data["sdp"], type=data["sdp_type"])
                    await pc.setRemoteDescription(offer)

                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    _logger.info("Call WebSocket: Sending SDP answer.")
                    await websocket.send_json({"type": "answer", "sdp": pc.localDescription.sdp})

                elif data["type"] == "ice":
                    _logger.info("Call WebSocket: Received ICE candidate.")
                    if data["candidate"]:
                        await pc.addIceCandidate(data["candidate"])
                        self.rtc_call_create_thread(pc)
                else:
                    _logger.warning("Call WebSocket: Unknown message type - %s", data["type"])

        except WebSocketDisconnect:
            _logger.info("Call WebSocket: Disconnected.")
        except Exception:
            _logger.exception("Call WebSocket: Unknown error occured")
        finally:
            if pc and pc.connectionState != "closed":
                await pc.close()
                _logger.info("Call WebSocket: Terminated. RTC peer connection also closed.")

    async def rtc_call_on_icecandidate(self, rtc_conn: UcaCallRTCPeerConnection, candidate):
        _logger.info("Call WebSocket: Sending ICE candidate: %s", candidate)
        if candidate:
            await rtc_conn.websocket.send_json({"type": "ice", "candidate": candidate.to_json()})

    async def rtc_call_on_track(self, rtc_conn: UcaCallRTCPeerConnection, track: MediaStreamTrack):
        _logger.info(
            "Call WebSocket: Track, id - %s, kind - %s received from remote peer.", track.id, track.kind
        )
        if track.kind == "audio":
            stt_request = self.stt_service.create_new_request()
            while True:
                await self.rtc_call_process_audio(rtc_conn, track, stt_request)

    async def rtc_call_process_audio(
        self, rtc_conn: UcaCallRTCPeerConnection, track: MediaStreamTrack, stt_request: BaseSTTRequest
    ):
        try:
            aframe: av.AudioFrame = await track.recv()
        except Exception:
            _logger.error("Call WebSocket: Can't receive audio track mostly socket closed.")
            return
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
        print("XXXxxxxXXX Silence detected")
        text = (
            self.stt_service.convert_request_to_text(stt_request)
            + " "
            + self.stt_service.flush_audio_in_request(stt_request)
        ).strip()
        if not text:
            return
        print("XXXxxxxXXX User text detected")
        rtc_conn.messages.append(
            OllamaChatMessage(role="user", content=text, agent_name=rtc_conn.messages[-1].agent_name)
        )
        task = asyncio.create_task(self.llm_chat_speak(rtc_conn))
        timer_task = asyncio.create_task(asyncio.sleep(_config.call_standby_message_timeout))

        done_async_tasks, pending_async_tasks = await asyncio.wait(
            [task, timer_task], return_when=asyncio.FIRST_COMPLETED
        )
        if task in pending_async_tasks and timer_task in done_async_tasks:
            # LLM Response taking longer than standby timer.
            # So respond with standby message
            rtc_conn.add_output_audio_frames(self.call_standby_message_audio)

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
        rtc_conn.add_output_audio_frames(aframe)
