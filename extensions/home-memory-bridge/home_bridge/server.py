"""Minimal OpenAI Chat Completions gateway for AIRI -> local llama.cpp.

No model inference happens here. We preserve the original request, adding
small sourced context, then relay the model's response without buffering audio
or waiting for a separate summarization model.
"""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from .store import data_home, get_api_key, init, memory_context, plain_text, save_exchange


UPSTREAM = os.getenv("HOME_UPSTREAM_URL", "http://127.0.0.1:8000/v1").rstrip("/")


def create_app(root: Path | None = None, transport: httpx.AsyncBaseTransport | None = None,
               upstream_url: str | None = None) -> FastAPI:
    root = root or data_home()
    init(root)
    token = get_api_key(root)
    upstream = (upstream_url or UPSTREAM).rstrip("/")
    app = FastAPI(title="Home Memory Bridge", docs_url=None, redoc_url=None)
    app.state.root = root

    # Calls carry a private bearer token; localhost-only binding is still
    # mandatory. Allow the AIRI Electron renderer's various dev origins.
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"],
                       allow_methods=["GET", "POST", "OPTIONS"], allow_credentials=False)

    def check_auth(request: Request) -> None:
        bearer = request.headers.get("authorization", "")
        provided = bearer[7:] if bearer.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(provided, token):
            raise HTTPException(status_code=401, detail="Home Memory Bridge: invalid API key")

    def get_client() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(10.0, read=None))

    def upstream_headers() -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if upstream_key := os.environ.get("HOME_UPSTREAM_API_KEY"):
            headers["authorization"] = "Bearer " + upstream_key
        return headers

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def models(request: Request) -> Response:
        check_auth(request)
        try:
            async with get_client() as client:
                r = await client.get(upstream + "/models", headers=upstream_headers())
                return Response(content=r.content, status_code=r.status_code,
                                media_type=r.headers.get("content-type", "application/json"))
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"Cannot reach llama.cpp: {exc}") from exc

    @app.post("/v1/chat/completions")
    async def completions(request: Request) -> Response:
        check_auth(request)
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400, "Invalid JSON request") from exc
        if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
            raise HTTPException(400, "Expected an OpenAI chat request with messages")

        original_messages: list[dict[str, Any]] = body["messages"]
        user_text = next((plain_text(m.get("content")) for m in reversed(original_messages)
                          if isinstance(m, dict) and m.get("role") == "user"), "")
        context = memory_context(root, user_text, original_messages)
        if context:
            # Keep all existing AIRI prompt/role/tool messages intact.
            body = {**body, "messages": list(original_messages)}
            index = 0
            while index < len(body["messages"]) and body["messages"][index].get("role") in ("system", "developer"):
                index += 1
            body["messages"].insert(index, {"role": "system", "content": context})

        model_name = str(body.get("model", "unknown"))
        if not body.get("stream", False):
            try:
                async with get_client() as client:
                    r = await client.post(upstream + "/chat/completions", json=body,
                                          headers=upstream_headers())
            except httpx.HTTPError as exc:
                raise HTTPException(502, f"Cannot reach llama.cpp: {exc}") from exc
            if r.is_success:
                try:
                    data = r.json()
                    answer = plain_text(data.get("choices", [{}])[0].get("message", {}).get("content", ""))
                    save_exchange(root, user_text, answer, model_name)
                except (ValueError, IndexError, KeyError, TypeError):
                    pass  # Do not break a legitimate model response to save a memory.
            return Response(content=r.content, status_code=r.status_code,
                            media_type=r.headers.get("content-type", "application/json"))

        # Open the upstream connection before sending 200 to the client so
        # backend errors retain their real status and body.
        client = get_client()
        try:
            req = client.build_request("POST", upstream + "/chat/completions", json=body,
                                       headers=upstream_headers())
            r = await client.send(req, stream=True)
        except httpx.HTTPError as exc:
            await client.aclose()
            raise HTTPException(502, f"Cannot reach llama.cpp: {exc}") from exc
        if not r.is_success:
            payload = await r.aread()
            status = r.status_code
            media = r.headers.get("content-type", "application/json")
            await r.aclose()
            await client.aclose()
            return Response(content=payload, status_code=status, media_type=media)

        async def relay():
            answer_parts: list[str] = []
            completed = False
            try:
                async for line in r.aiter_lines():
                    # Forward exactly the newline-delimited SSE framing.
                    # Do not delay user-visible audio/text for memory storage.
                    yield line + "\n"
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        completed = True
                        continue
                    try:
                        event = json.loads(data)
                        for choice in event.get("choices", []):
                            delta = choice.get("delta", {})
                            fragment = delta.get("content", "")
                            if isinstance(fragment, str):
                                answer_parts.append(fragment)
                    except (json.JSONDecodeError, TypeError, AttributeError):
                        continue
            finally:
                await r.aclose()
                await client.aclose()
                # Do not remember partial responses or failed streams.
                if completed:
                    save_exchange(root, user_text, "".join(answer_parts), model_name)

        return StreamingResponse(relay(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


