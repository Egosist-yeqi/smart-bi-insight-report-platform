import json

import httpx
import pytest

from app.ai.client import AIClientError, OpenAICompatibleClient


def _chat_completion(request: httpx.Request) -> httpx.Response:
    assert request.url == "https://provider.example/v1/chat/completions"
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


@pytest.mark.asyncio
async def test_client_normalizes_base_url_and_returns_intent():
    client = OpenAICompatibleClient(
        base_url="https://provider.example/v1/",
        api_key="test-client-key",
        model="demo-model",
        timeout_seconds=5,
        transport=httpx.MockTransport(_chat_completion),
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
    )

    with pytest.raises(AIClientError) as error:
        await client.resolve_intent("任何问题")

    assert error.value.code == "AI_AUTH_FAILED"
    assert "test-client-key" not in str(error.value)
