import logging
from datetime import datetime, timezone
from typing import Literal

import httpx
import orjson
from openg2p_fastapi_common.service import BaseService

from ..config import Settings
from ..errors import GetMessagesMissingParamsError
from ..schemas.chat import ChatMessage, ChatThread, GetChatMessageResponse, GetChatThreadResponse

_config = Settings.get_config(strict=False)
_logger = logging.getLogger(_config.logging_default_logger_name)


class ChatStoreService(BaseService):
    def __init__(self, **kwargs):
        """
        Abstract Service. Donot instantiate directly.
        """
        super().__init__(**kwargs)
        self.enabled: bool = True

    async def initialize(self):
        raise NotImplementedError()

    async def aclose(self):
        raise NotImplementedError()

    async def migrate(self):
        raise NotImplementedError()

    async def get_messages(
        self,
        thread_id: str = "",
        message_id: str = "",
        user_id: str = "",
        message_by: list[str] | None = None,
        limit: int = 10,
        page: int = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> GetChatMessageResponse:
        """
        Any combination of thread_id, message_id, user_id, message_by search should work
        """
        raise NotImplementedError()

    async def put_message(self, chat_message: ChatMessage):
        raise NotImplementedError()

    async def get_threads(
        self,
        user_id: str = "",
        thread_id: str = "",
        limit: int = 10,
        page: int = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> GetChatThreadResponse:
        """
        Any combination of thread_id, user_id search should work
        """
        raise NotImplementedError()

    async def put_thread(self, chat_thread: ChatThread):
        raise NotImplementedError()


class ESChatStoreService(ChatStoreService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.enabled = _config.chat_store_es_enabled
        self.client: httpx.AsyncClient = None

    async def initialize(self):
        self.client = httpx.AsyncClient(
            auth=(_config.chat_store_es_username, _config.chat_store_es_password)
            if _config.chat_store_es_username
            else None,
            verify=_config.chat_store_es_ssl_verify,
        )

    async def aclose(self):
        await self.client.aclose()

    async def migrate(self):
        await self.initialize()
        await self.create_or_update_index_mapping(
            _config.chat_store_messages_es_index,
            {
                "properties": {
                    "id": {"type": "keyword"},
                    "thread_id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "sent_at": {"type": "date", "format": "strict_date_time"},
                    "message_by": {"type": "keyword"},
                    "message": {"type": "text"},
                    "tool_name": {"type": "keyword"},
                }
            },
        )
        await self.create_or_update_index_mapping(
            _config.chat_store_threads_es_index,
            {
                "properties": {
                    "id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "created_at": {"type": "date", "format": "strict_date_time"},
                }
            },
        )
        await self.aclose()

    async def create_or_update_index_mapping(self, index: str, mapping: dict):
        # Check if the index exists
        res = await self.client.head(f"{_config.chat_store_es_url}/{index}")
        if res.status_code == 404:
            index_exists = False
        else:
            index_exists = True
            res.raise_for_status()

        if not index_exists:
            _logger.info("Chat Store ES: Index doesn't exist. Creating...")
            res = await self.client.put(f"{_config.chat_store_es_url}/{index}", json={"mappings": mapping})
        else:
            _logger.info("Chat Store ES: Index already exists. Updating mapping...")
            res = await self.client.put(f"{_config.chat_store_es_url}/{index}/_mapping", json=mapping)
        res.raise_for_status()

    async def get_messages(
        self,
        thread_id: str = "",
        message_id: str = "",
        user_id: str = "",
        message_by: list[str] | None = None,
        limit: int = 10,
        page: int = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> GetChatMessageResponse:
        must_match = []
        if thread_id:
            must_match.append({"term": {"thread_id": {"value": thread_id}}})
        if message_id:
            must_match.append({"term": {"id": {"value": message_id}}})
        if user_id:
            must_match.append({"term": {"user_id": {"value": user_id}}})
        if message_by:
            msg_by_match = []
            for msg_by in message_by:
                msg_by_match.append({"term": {"message_by": {"value": msg_by}}})
            must_match.append({"bool": {"should": msg_by_match}})

        if not must_match:
            raise GetMessagesMissingParamsError()

        if limit < 0:
            limit = _config.chat_store_messages_limit
        query = {
            "query": {"bool": {"must": must_match}},
            "from": limit * page,
            "size": limit,
            "sort": [{"sent_at": {"order": sort}}],
        }
        res = await self.es_search(query, _config.chat_store_messages_es_index)
        # TODO: Handle es search API size limit problem

        total_count = ((res.get("hits") or {}).get("total") or {}).get("value") or 0
        hits = (res.get("hits") or {}).get("hits") or []

        messages = [ChatMessage.model_validate(hit.get("_source") or {}) for hit in hits]

        return GetChatMessageResponse(
            count=len(hits),
            total_count=total_count,
            messages=messages,
            thread_id=thread_id,
            user_id=user_id,
        )

    async def put_message(self, chat_message: ChatMessage):
        await self.es_put_by_id(
            chat_message.model_dump(mode="json"), chat_message.id, _config.chat_store_messages_es_index
        )

    async def get_threads(
        self,
        user_id: str = "",
        thread_id: str = "",
        limit: int = 10,
        page: int = 0,
        sort: Literal["asc", "desc"] = "desc",
    ) -> GetChatThreadResponse:
        must_match = []
        if thread_id:
            must_match.append({"term": {"id": {"value": thread_id}}})
        if user_id:
            must_match.append({"term": {"user_id": {"value": user_id}}})

        if not must_match:
            raise GetMessagesMissingParamsError()

        if limit < 0:
            limit = _config.chat_store_messages_limit
        query = {
            "query": {"bool": {"must": must_match}},
            "from": limit * page,
            "size": limit,
            "sort": [{"created_at": {"order": sort}}],
        }
        res = await self.es_search(query, _config.chat_store_threads_es_index)
        # TODO: Handle es search API size limit problem

        total_count = ((res.get("hits") or {}).get("total") or {}).get("value") or 0
        hits = (res.get("hits") or {}).get("hits") or []

        threads = [ChatThread.model_validate(hit.get("_source") or {}) for hit in hits]

        return GetChatThreadResponse(
            count=len(hits),
            total_count=total_count,
            threads=threads,
            user_id=user_id,
        )

    async def put_thread(self, chat_thread: ChatThread):
        await self.es_put_by_id(
            chat_thread.model_dump(mode="json"), chat_thread.id, _config.chat_store_threads_es_index
        )

    async def es_search(self, query: dict, index: str) -> dict:
        res = await self.client.request(
            "GET",
            f"{_config.chat_store_es_url}/{index}/_search",
            headers={"content-type": "application/json"},
            content=orjson.dumps(query),
            timeout=_config.chat_store_es_timeout_secs,
        )
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return orjson.loads(res.text)

    async def es_put_by_id(
        self,
        body: dict,
        id,
        index,
        insert_times=False,
        refresh: Literal["true", "false", "wait_for"] = "true",
    ):
        if insert_times:
            now = self.get_curr_timestamp()
            json_body = {
                "doc": {"updated_at": now, "@timestamp": now, **body},
                "upsert": {"created_at": now, "updated_at": None, "@timestamp": now, **body},
            }
        else:
            json_body = {
                "doc": body,
                "doc_as_upsert": True,
            }
        res = await self.client.post(
            f"{_config.chat_store_es_url}/{index}/_update/{id}?refresh={refresh}",
            timeout=_config.chat_store_es_timeout_secs,
            headers={"content-type": "application/json"},
            content=orjson.dumps(json_body),
        )
        res.raise_for_status()

    def get_curr_timestamp(self) -> str:
        now = datetime.now(tz=timezone.utc)
        now = now.isoformat(timespec="milliseconds") + "Z"
        return now
