import json

import httpx
import pytest

from app.ai.client import AIClientError, OpenAICompatibleClient


async def _global_resolver(_hostname: str, _port: int) -> set[str]:
    return {"8.8.8.8"}


def _chat_completion(request: httpx.Request) -> httpx.Response:
    assert request.url == "https://8.8.8.8/v1/chat/completions"
    assert request.headers["host"] == "provider.example"
    assert request.extensions["sni_hostname"] == "provider.example"
    assert request.headers["authorization"] == "Bearer test-client-key"
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "metric": "amount",
                                "dimensions": ["region"],
                                "time_range": "latest_month",
                            }
                        )
                    }
                }
            ]
        },
    )


def _any_url_chat_completion(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {"metric": "amount", "dimensions": ["region"]}
                        )
                    }
                }
            ]
        },
    )


@pytest.mark.asyncio
async def test_client_normalizes_base_url_and_returns_intent():
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1/",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(_chat_completion),
        dns_resolver=_global_resolver,
    )

    intent = await client.resolve_intent("本月各区域销售额排名如何？")

    assert intent.metric == "amount"
    assert intent.dimensions == ["region"]


@pytest.mark.asyncio
async def test_client_rejects_oversized_or_invalid_intent_responses():
    async def oversized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Length": "1048577"})

    client = OpenAICompatibleClient(
        base_url="http://mock-llm:8090",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(oversized),
        dns_resolver=_global_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_BAD_RESPONSE"


@pytest.mark.asyncio
async def test_client_maps_authentication_status_without_including_key():
    client = OpenAICompatibleClient(
        base_url="https://provider.example",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
        dns_resolver=_global_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_AUTH_FAILED"
    assert "test-client-key" not in str(error.value)


@pytest.mark.asyncio
async def test_client_blocks_private_networks_without_explicit_opt_in():
    async def private_resolver(_hostname: str, _port: int) -> set[str]:
        return {"127.0.0.1"}

    client = OpenAICompatibleClient(
        base_url="http://mock-llm:8090/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(_any_url_chat_completion),
        dns_resolver=private_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_SSRF_BLOCKED"


@pytest.mark.asyncio
async def test_client_validates_every_resolved_address_before_connecting():
    async def mixed_resolver(_hostname: str, _port: int) -> set[str]:
        return {"8.8.8.8", "127.0.0.1"}

    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(
            lambda _request: pytest.fail("unsafe mixed DNS result reached transport")
        ),
        dns_resolver=mixed_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_SSRF_BLOCKED"


@pytest.mark.asyncio
async def test_client_pins_the_validated_address_without_a_second_dns_lookup():
    resolver_calls = 0

    async def rebinding_resolver(_hostname: str, _port: int) -> set[str]:
        nonlocal resolver_calls
        resolver_calls += 1
        return {"8.8.8.8"} if resolver_calls == 1 else {"127.0.0.1"}

    def assert_pinned_connection(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "8.8.8.8"
        assert request.headers["host"] == "provider.example"
        assert request.extensions["sni_hostname"] == "provider.example"
        return _any_url_chat_completion(request)

    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(assert_pinned_connection),
        dns_resolver=rebinding_resolver,
    )

    intent = await client.resolve_intent("任何问题")

    assert intent.metric == "amount"
    assert resolver_calls == 1


@pytest.mark.asyncio
async def test_client_allows_private_mock_only_when_explicitly_opted_in():
    async def private_resolver(_hostname: str, _port: int) -> set[str]:
        return {"172.20.0.4"}

    client = OpenAICompatibleClient(
        base_url="http://mock-llm:8090/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        allow_private_network=True,
        transport=httpx.MockTransport(_any_url_chat_completion),
        dns_resolver=private_resolver,
    )

    intent = await client.resolve_intent("任何问题")

    assert intent.metric == "amount"


@pytest.mark.asyncio
async def test_client_revalidates_redirects_and_never_forwards_cross_origin_credentials():
    calls = []

    async def resolver(hostname: str, _port: int) -> set[str]:
        return {"8.8.8.8"} if hostname == "provider.example" else {"127.0.0.1"}

    def redirect(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://private.example/v1/next"})

    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(redirect),
        dns_resolver=resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_SSRF_BLOCKED"
    assert len(calls) == 1
    assert calls[0].headers["authorization"] == "Bearer test-client-key"


@pytest.mark.asyncio
async def test_client_reuses_the_pinned_address_for_same_origin_redirects():
    resolver_calls = 0
    requests = []

    async def rebinding_resolver(_hostname: str, _port: int) -> set[str]:
        nonlocal resolver_calls
        resolver_calls += 1
        return {"8.8.8.8"} if resolver_calls == 1 else {"127.0.0.1"}

    def same_origin_redirect(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(307, headers={"Location": "/v1/retry"})
        return _any_url_chat_completion(request)

    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(same_origin_redirect),
        dns_resolver=rebinding_resolver,
    )

    intent = await client.resolve_intent("任何问题")

    assert intent.metric == "amount"
    assert resolver_calls == 1
    assert [request.url.host for request in requests] == ["8.8.8.8", "8.8.8.8"]
    assert all(request.headers["host"] == "provider.example" for request in requests)


@pytest.mark.asyncio
async def test_client_enforces_the_five_redirect_limit():
    calls = []

    def redirect(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(302, headers={"Location": "/v1/retry"})

    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(redirect),
        dns_resolver=_global_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_BAD_RESPONSE"
    assert len(calls) == 6


@pytest.mark.asyncio
async def test_client_aborts_streamed_responses_over_the_cumulative_limit():
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"x" * 1_048_577)
        ),
        dns_resolver=_global_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_BAD_RESPONSE"


@pytest.mark.asyncio
async def test_client_accepts_only_structured_narratives_grounded_in_local_facts():
    local_facts = "销售额1,200.00元，毛利率20.00%。"
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps({"narrative": local_facts})}}]}
            )
        ),
        dns_resolver=_global_resolver,
    )

    narrative = await client.generate_narrative("概览", local_facts)

    assert narrative == local_facts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        {"metric": "amount", "dimensions": ["region"]},
        {"narrative": "销售额9,999.00元。"},
        "任意文本",
    ],
)
async def test_client_rejects_ungrounded_or_unstructured_narratives(content):
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(content) if isinstance(content, dict) else content}}]}
            )
        ),
        dns_resolver=_global_resolver,
    )

    with pytest.raises(AIClientError) as error:
        await client.generate_narrative("概览", "销售额1,200.00元。")

    assert error.value.code == "AI_BAD_RESPONSE"
