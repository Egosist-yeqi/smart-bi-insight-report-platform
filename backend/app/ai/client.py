import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.ai.schemas import normalize_base_url
from app.core.errors import AppError
from app.query.schemas import QueryIntent


MAX_RESPONSE_BYTES = 1_048_576


class AIClientError(AppError):
    def __init__(self, code: str, message: str, status_code: int = 502) -> None:
        super().__init__(code=code, message=message, status_code=status_code)


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self._api_key = api_key
        self.model = model
        self._transport = transport
        self._timeout = httpx.Timeout(
            connect=timeout_seconds,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=timeout_seconds,
        )

    async def resolve_intent(self, question: str) -> QueryIntent:
        content = await self._completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Return only one JSON object matching the QueryIntent schema. "
                        "Do not return SQL, markdown, commentary, or code fences."
                    ),
                },
                {"role": "user", "content": question},
            ]
        )
        try:
            return QueryIntent.model_validate_json(content)
        except (ValidationError, ValueError, TypeError) as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回的查询意图无效。") from exc

    async def test_connection(self) -> None:
        await self.resolve_intent("请返回按区域汇总本月销售额的查询意图。")

    async def generate_narrative(self, title: str, local_facts: str) -> str:
        content = await self._completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Write a brief Chinese business narrative. Preserve all numeric facts "
                        "from the supplied local facts and do not invent measurements."
                    ),
                },
                {"role": "user", "content": f"标题：{title}\n本地事实：{local_facts}"},
            ]
        )
        if not content.strip():
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回的报告叙述为空。")
        return content

    async def _completion(self, messages: list[dict[str, str]]) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=True,
                follow_redirects=True,
                max_redirects=5,
                transport=self._transport,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"model": self.model, "temperature": 0, "messages": messages},
                ) as response:
                    self._raise_for_status(response)
                    self._validate_content_length(response)
                    body = await response.aread()
        except AIClientError:
            raise
        except httpx.TimeoutException as exc:
            raise AIClientError("AI_TIMEOUT", "AI 服务请求超时。", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务请求失败。") from exc

        if len(body) > MAX_RESPONSE_BYTES:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回内容超过大小限制。")
        try:
            payload: dict[str, Any] = json.loads(body)
            content = payload["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回格式不兼容。") from exc
        if not isinstance(content, str):
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回格式不兼容。")
        return content

    @staticmethod
    def _validate_content_length(response: httpx.Response) -> None:
        content_length = response.headers.get("Content-Length")
        if content_length is None:
            return
        try:
            length = int(content_length)
        except ValueError as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回内容长度无效。") from exc
        if length < 0 or length > MAX_RESPONSE_BYTES:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回内容超过大小限制。")

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status_messages = {
            401: ("AI_AUTH_FAILED", "AI API 密钥无效。", 401),
            403: ("AI_AUTH_FAILED", "AI API 密钥无效。", 403),
            404: ("AI_MODEL_NOT_FOUND", "AI 模型或服务地址不存在。", 404),
            429: ("AI_RATE_LIMITED", "AI 服务请求过于频繁。", 429),
        }
        if response.status_code in status_messages:
            code, message, status_code = status_messages[response.status_code]
            raise AIClientError(code, message, status_code=status_code)
        if response.is_error:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务返回异常状态。")
