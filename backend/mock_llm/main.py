import json

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    temperature: int | float


@app.post("/v1/chat/completions")
def chat_completions(
    payload: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    if authorization != "Bearer test-key":
        raise HTTPException(status_code=401, detail="Unauthorized")
    system_prompt = payload.messages[0]["content"] if payload.messages else ""
    if "QueryIntent" in system_prompt:
        content = {
            "metric": "amount",
            "dimensions": ["region"],
            "time_range": "latest_month",
            "analysis_kind": "ranking",
        }
    else:
        user_prompt = payload.messages[-1]["content"] if payload.messages else ""
        content = {"narrative": user_prompt.split("本地事实：", 1)[-1]}
    return {
        "id": "mock-chat-completion",
        "object": "chat.completion",
        "model": payload.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(content),
                },
                "finish_reason": "stop",
            }
        ],
    }
