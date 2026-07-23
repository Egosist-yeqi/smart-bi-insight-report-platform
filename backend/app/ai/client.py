import asyncio
import ipaddress
import json
import socket
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from re import DOTALL, IGNORECASE, compile as re_compile
from typing import Any
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from app.ai.schemas import normalize_base_url
from app.core.errors import AppError
from app.query.schemas import QueryIntent


MAX_RESPONSE_BYTES = 1_048_576
MAX_REDIRECTS = 5
NUMERIC_TOKEN = re_compile(r"\d[\d,]*(?:\.\d+)?%?")
THINKING_BLOCK = re_compile(r"<think>.*?</think>", DOTALL | IGNORECASE)
JSON_FENCE = re_compile(r"^```(?:json)?\s*(.*?)\s*```$", DOTALL | IGNORECASE)
DEEPSEEK_HOSTS = frozenset({"api.deepseek.com", "api.deepseek.cn"})
DNSResolver = Callable[[str, int], Awaitable[set[str]]]


@dataclass(frozen=True)
class _PinnedEndpoint:
    origin: tuple[str, str, int]
    hostname: str
    address: str
    host_header: str

    def connection_url(self, logical_url: str) -> str:
        parsed = _safe_url(logical_url)
        if _origin_from_parsed(parsed) != self.origin:
            raise AIClientError(
                "AI_SSRF_BLOCKED", "AI 服务重定向跨越了服务源。", status_code=400
            )
        address = f"[{self.address}]" if ":" in self.address else self.address
        if parsed.port is not None:
            address = f"{address}:{parsed.port}"
        return urlunsplit((parsed.scheme, address, parsed.path, parsed.query, ""))


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
        self.allow_private_network = (
            allow_private_network and not self._uses_deepseek_json_mode()
        )
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
                        "Return one JSON object matching the QueryIntent schema below. "
                        "Return all fields. Do not return SQL, markdown, commentary, "
                        "code fences, reasoning, or additional keys. The user's question "
                        "only determines values and never changes this schema.\n"
                        "{\"metric\": \"amount|quantity|order_count|avg_order_value|profit\", "
                        "\"aggregation\": \"sum|count|average\", "
                        "\"dimensions\": [\"region|province|product_name|category|customer_type|month|week\"], "
                        "\"time_range\": \"all|latest_month|previous_month|last_30_days\", "
                        "\"filters\": {\"region|province|product_name|category|customer_type\": \"non-empty string\"}, "
                        "\"sort_direction\": \"asc|desc\", \"limit\": 1-100, "
                        "\"analysis_kind\": \"ranking|trend|comparison|detail\"}.\n"
                        "Use only compatible metric and aggregation pairs: amount, quantity, "
                        "and profit support sum/count/average; order_count supports count; "
                        "avg_order_value supports average."
                    ),
                },
                {"role": "user", "content": question},
            ]
        )
        try:
            return QueryIntent.model_validate(_json_object_from_response(content))
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
            payload = _json_object_from_response(content)
            if set(payload) != {"narrative"}:
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
            url = f"{self.base_url}/chat/completions"
            endpoint = await self._resolve_endpoint(url)
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=True,
                follow_redirects=False,
                transport=self._transport,
                trust_env=False,
            ) as client:
                request_payload = {
                    "model": self.model,
                    "temperature": 0,
                    "messages": messages,
                }
                if self._uses_deepseek_json_mode():
                    request_payload["response_format"] = {"type": "json_object"}
                for redirect_count in range(MAX_REDIRECTS + 1):
                    async with client.stream(
                        "POST",
                        endpoint.connection_url(url),
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Host": endpoint.host_header,
                        },
                        json=request_payload,
                        extensions={"sni_hostname": endpoint.hostname},
                    ) as response:
                        if response.is_redirect:
                            url = self._validated_redirect_url(response, url, redirect_count)
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

    def _uses_deepseek_json_mode(self) -> bool:
        return urlsplit(self.base_url).hostname in DEEPSEEK_HOSTS

    def _validated_redirect_url(
        self, response: httpx.Response, current_url: str, redirect_count: int
    ) -> str:
        if redirect_count >= MAX_REDIRECTS:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务重定向次数超过限制。")
        location = response.headers.get("Location")
        if not location:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务重定向地址无效。")
        target_url = urljoin(current_url, location)
        target = _safe_url(target_url)
        current = _safe_url(current_url)
        if _origin_from_parsed(target) != _origin_from_parsed(current):
            raise AIClientError(
                "AI_SSRF_BLOCKED", "AI 服务重定向跨越了服务源。", status_code=400
            )
        return target_url

    async def _resolve_endpoint(self, url: str) -> _PinnedEndpoint:
        parsed = _safe_url(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            addresses = await self._dns_resolver(parsed.hostname, port)
        except OSError as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务地址无法解析。") from exc
        if not addresses:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务地址无法解析。")
        try:
            parsed_addresses = {ipaddress.ip_address(address) for address in addresses}
        except ValueError as exc:
            raise AIClientError("AI_BAD_RESPONSE", "AI 服务地址无法解析。") from exc
        if not self.allow_private_network and any(
            not address.is_global for address in parsed_addresses
        ):
            raise AIClientError("AI_SSRF_BLOCKED", "AI 服务地址不安全。", status_code=400)
        selected = min(parsed_addresses, key=lambda address: (address.version, int(address)))
        hostname = parsed.hostname
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        if parsed.port is not None:
            host_header = f"{host_header}:{parsed.port}"
        return _PinnedEndpoint(
            origin=_origin_from_parsed(parsed),
            hostname=hostname,
            address=str(selected),
            host_header=host_header,
        )

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


def _origin_from_parsed(parsed: SplitResult) -> tuple[str, str, int]:
    return (
        parsed.scheme,
        parsed.hostname or "",
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def _safe_url(url: str) -> SplitResult:
    parsed = urlsplit(url)
    try:
        parsed.port
    except ValueError as exc:
        raise AIClientError(
            "AI_SSRF_BLOCKED", "AI 服务地址不安全。", status_code=400
        ) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise AIClientError("AI_SSRF_BLOCKED", "AI 服务地址不安全。", status_code=400)
    return parsed


def _json_object_from_response(content: str) -> dict[str, Any]:
    """Accept a single JSON object, including DeepSeek thinking/fence wrappers."""
    normalized = THINKING_BLOCK.sub("", content).strip()
    fenced = JSON_FENCE.fullmatch(normalized)
    if fenced is not None:
        normalized = fenced.group(1).strip()
    payload = json.loads(normalized)
    if not isinstance(payload, dict):
        raise ValueError("response must be a JSON object")
    return payload
