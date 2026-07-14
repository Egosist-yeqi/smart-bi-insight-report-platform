import asyncio
import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ai.client import OpenAICompatibleClient
from app.ai.schemas import (
    AIConnectionResult,
    AIProviderInput,
    AIProviderTestInput,
    AIProviderView,
)
from app.core.config import get_settings
from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.core.errors import AppError
from app.db.models import AIProviderConfig
from app.query.schemas import QueryIntent
from app.reports.schemas import ReportSection


class AIProviderKeyRequiredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_API_KEY_REQUIRED",
            message="首次保存 AI 服务配置时必须提供 API 密钥。",
            status_code=400,
        )


class AIConfigurationError(AppError):
    def __init__(self) -> None:
        super().__init__(
            code="AI_CONFIGURATION_INVALID",
            message="AI 配置无效，请重新保存配置。",
            status_code=400,
        )


def get_provider_view(session: Session) -> AIProviderView:
    provider = session.get(AIProviderConfig, 1)
    if provider is None:
        return AIProviderView(configured=False, ai_mode="local")
    return _provider_view(provider)


def save_provider(session: Session, payload: AIProviderInput) -> AIProviderView:
    provider = session.get(AIProviderConfig, 1)
    supplied_key = (payload.api_key or "").strip()
    if provider is None:
        if not supplied_key:
            raise AIProviderKeyRequiredError()
        provider = AIProviderConfig(
            id=1,
            provider_name=payload.provider_name,
            base_url=payload.base_url,
            model=payload.model,
            encrypted_api_key=encrypt_secret(supplied_key, get_settings().app_encryption_key),
            api_key_hint=mask_secret(supplied_key),
            enabled=payload.enabled,
            allow_private_network=payload.allow_private_network,
            timeout_seconds=payload.timeout_seconds,
        )
        session.add(provider)
    else:
        provider.provider_name = payload.provider_name
        provider.base_url = payload.base_url
        provider.model = payload.model
        provider.enabled = payload.enabled
        provider.allow_private_network = payload.allow_private_network
        provider.timeout_seconds = payload.timeout_seconds
        if supplied_key:
            provider.encrypted_api_key = encrypt_secret(
                supplied_key, get_settings().app_encryption_key
            )
            provider.api_key_hint = mask_secret(supplied_key)

    session.commit()
    session.refresh(provider)
    return _provider_view(provider)


def delete_provider(session: Session) -> AIProviderView:
    provider = session.get(AIProviderConfig, 1)
    if provider is not None:
        session.delete(provider)
        session.commit()
    return AIProviderView(configured=False, ai_mode="local")


def test_provider(session: Session, payload: AIProviderTestInput) -> AIConnectionResult:
    client, provider_name, model = _client_for_test(session, payload)
    started_at = time.perf_counter()
    _run(client.test_connection())
    return AIConnectionResult(
        status="connected",
        provider=provider_name,
        model=model,
        latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
        enabled=payload.enabled,
        allow_private_network=payload.allow_private_network,
    )


def get_intent_resolver(session: Session) -> Callable[[str], QueryIntent] | None:
    provider = _enabled_provider(session)
    if provider is None:
        return None
    client = _client_for_provider(provider)

    def resolve(question: str) -> QueryIntent:
        return _run(client.resolve_intent(question))

    return resolve


def get_report_narrative(session: Session) -> Callable[[ReportSection], str | None] | None:
    provider = _enabled_provider(session)
    if provider is None:
        return None
    client = _client_for_provider(provider)

    def narrative(section: ReportSection) -> str:
        return _run(client.generate_narrative(section.title, section.content))

    return narrative


def _enabled_provider(session: Session) -> AIProviderConfig | None:
    provider = session.get(AIProviderConfig, 1)
    return provider if provider is not None and provider.enabled else None


def _client_for_test(
    session: Session, payload: AIProviderTestInput
) -> tuple[OpenAICompatibleClient, str, str]:
    api_key = (payload.api_key or "").strip()
    if not api_key:
        provider = session.get(AIProviderConfig, 1)
        if provider is None:
            raise AIProviderKeyRequiredError()
        api_key = _provider_api_key(provider)
    return (
        OpenAICompatibleClient(
            base_url=payload.base_url,
            api_key=api_key,
            model=payload.model,
            timeout_seconds=payload.timeout_seconds,
            allow_private_network=payload.allow_private_network,
        ),
        payload.provider_name,
        payload.model,
    )


def _client_for_provider(provider: AIProviderConfig) -> OpenAICompatibleClient:
    api_key = _provider_api_key(provider)
    return OpenAICompatibleClient(
        base_url=provider.base_url,
        api_key=api_key,
        model=provider.model,
        timeout_seconds=provider.timeout_seconds,
        allow_private_network=provider.allow_private_network,
    )


def _provider_api_key(provider: AIProviderConfig) -> str:
    try:
        return decrypt_secret(
            provider.encrypted_api_key, get_settings().app_encryption_key
        )
    except AppError:
        raise AIConfigurationError() from None


def _provider_view(provider: AIProviderConfig) -> AIProviderView:
    return AIProviderView(
        configured=True,
        ai_mode="ai" if provider.enabled else "local",
        provider_name=provider.provider_name,
        base_url=provider.base_url,
        model=provider.model,
        timeout_seconds=provider.timeout_seconds,
        enabled=provider.enabled,
        allow_private_network=provider.allow_private_network,
        api_key_hint=provider.api_key_hint,
    )


def _run(coroutine):
    return asyncio.run(coroutine)
