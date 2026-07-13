import asyncio
import ipaddress
import json
import socket
from collections import Counter
from collections.abc import Awaitable, Callable
from re import compile as re_compile
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from pydantic import ValidationError

from app.ai.schemas import normalize_base_url
from app.core.errors import AppError
from app.query.schemas import QueryIntent


MAX_RESPONSE_BYTES = 1_048_576
MAX_REDIRECTS = 5
NUMERIC_TOKEN = re_compile(r"\d[\d,]*(?:\.\d+)?%?")
DNSResolver = Callable[[str, int], Awaitable[set[str]]]


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
        allow_private_network: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        dns_resolver: DNSResolver | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self._api_key = api_key
        self.model = model
        self.allow_private_network = allow_private_network
        self._transport = transport
        self._dns_resolver = dns_resolver or _resolve_all_addresses
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
                        "Return only one JSON object with exactly one key, narrative. The Chinese "
                        "narrative must preserve every numeric token from the supplied local facts "
                        "exactly and must not invent any measurements."
                    ),
                },
                {"role": "user", "content": f"标题：{title}\n本地事实：{local_facts}"},
            ]
        )
        try:
            payload = json.loads(content)
            if not isinstance(payload, dict) or set(payload) != {"narrative"}:
                raise ValueError("unexpected narrative shape")
            narrative = payload["narrative"]
            if not isinstance(narrative, str) or not narrative.strip():
                raise ValueError("empty narrative")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回的报告叙述无效。") from exc
        if Counter(NUMERIC_TOKEN.findall(narrative)) != Counter(NUMERIC_TOKEN.findall(local_facts)):
            raise AIClientError("AI_BAD_RESPONSE", "AI 报告叙述包含未经验证的数值。")
        return narrative

    async def _completion(self, messages: list[dict[str, str]]) -> str:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=True,
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                url = f"{self.base_url}/chat/completions"
                request_payload = {
                    "model": self.model,
                    "temperature": 0,
                    "messages": messages,
                }
                for redirect_count in range(MAX_REDIRECTS + 1):
                    await self._assert_safe_endpoint(url)
                    async with client.stream(
                        "POST",
                        url,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=request_payload,
                    ) as response:
                        if response.is_redirect:
                            url = await self._validated_redirect_url(
                                response, url, redirect_count
                            )
                            continue
                        self._raise_for_status(response)
                        self._validate_content_length(response)
                        body = await self._read_limited_body(response)
                        break
                else:
                    raise AIClientError("AI_BAD_RESPONSE", "AI 服务重定向次数超过限制。")
        except AIClientError:
            raise
        except httpx.TimeoutException as exc:
            raise AIClientError("AI_TIMEOUT", "AI 服务请求超时。", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务请求失败。") from exc

        try:
            payload: dict[str, Any] = json.loads(body)
            content = payload["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回格式不兼容。") from exc
        if not isinstance(content, str):
            raise AIClientError("AI_BAD_RESPONSE", "AI 返回格式不兼容。")
        return content

    async def _validated_redirect_url(
        self, response: httpx.Response, current_url: str, redirect_count: int
    ) -> str:
        if redirect_count >= MAX_REDIRECTS:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务重定向次数超过限制。")
        location = response.headers.get("Location")
        if not location:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务重定向地址无效。")
        target_url = urljoin(current_url, location)
        await self._assert_safe_endpoint(target_url)
        if _origin(target_url) != _origin(current_url):
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务重定向跨越了服务源。")
        return target_url

    async def _assert_safe_endpoint(self, url: str) -> None:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AIClientError("AI_SSRF_BLOCKED", "AI 服务地址不安全。", status_code=400)
        try:
            addresses = await self._dns_resolver(
                parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
            )
        except OSError as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务地址无法解析。") from exc
        if not addresses:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务地址无法解析。")
        if not self.allow_private_network and any(
            not ipaddress.ip_address(address).is_global for address in addresses
        ):
            raise AIClientError("AI_SSRF_BLOCKED", "AI 服务地址不安全。", status_code=400)

    @staticmethod
    async def _read_limited_body(response: httpx.Response) -> bytes:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > MAX_RESPONSE_BYTES:
                raise AIClientError("AI_BAD_RESPONSE", "AI 返回内容超过大小限制。")
        return bytes(body)

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


async def _resolve_all_addresses(hostname: str, port: int) -> set[str]:
    def resolve() -> set[str]:
        return {
            entry[4][0]
            for entry in socket.getaddrinfo(
                hostname, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
            )
        }

    return await asyncio.to_thread(resolve)


def _origin(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    return (
        parsed.scheme,
        parsed.hostname or "",
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )
