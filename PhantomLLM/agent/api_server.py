"""
api_server.py – FastAPI server with full OpenAI-compatible endpoints.

Endpoints
─────────
POST /v1/chat/completions   OpenAI-compatible chat endpoint  (MANDATORY)
GET  /v1/models             List all available model identifiers
GET  /status                Browser / worker health check
POST /message               Legacy single-message endpoint (backward compat)

The server is fully async.  Synchronous provider calls (Playwright worker,
third-party SDKs) are offloaded to a thread-pool executor so they never
block the asyncio event loop.

Startup behaviour
─────────────────
If cfg.default_model is an openai_ui variant, the Playwright worker is
started automatically during app lifespan so the browser is ready before
the first request arrives.

OpenAI schema compliance
─────────────────────────
POST /v1/chat/completions strictly follows the OpenAI Chat Completions spec:
    https://platform.openai.com/docs/api-reference/chat/create
Response fields that are unavailable for browser/local providers (e.g. token
counts) are returned as 0 rather than omitted, for maximum client compat.
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.config.settings import cfg
from agent.models.router import generate, PROVIDER_MAP


# ── Pydantic request / response models ───────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message in an OpenAI-style conversation."""
    role:    str
    content: str


class ChatCompletionRequest(BaseModel):
    """
    OpenAI /v1/chat/completions request body.
    Only the fields we actually use are declared; extras are silently ignored.
    """
    model:       str             = "gpt-4"
    messages:    list[ChatMessage]
    max_tokens:  Optional[int]   = 4096
    temperature: Optional[float] = 0.7
    timeout:     Optional[int]   = 180     # Extension: per-request timeout (s)


class LegacyMessageRequest(BaseModel):
    """Request body for the legacy /message endpoint."""
    text:    str
    timeout: Optional[int] = 180


# ── Lifespan (startup / shutdown hooks) ──────────────────────────────────────

_BROWSER_MODELS = frozenset({
    "openai_ui", "claude_ui", "gemini_ui", "deepseek_ui",
    "grok_ui", "qwen_ui", "perplexity_ui",
})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: if the default model uses a browser, start the Playwright worker,
    open the provider tab, and inject the system context — so the server is fully
    ready before the first HTTP request arrives.
    On shutdown: nothing (worker thread is daemonised and exits with the process).
    """
    model = cfg.default_model

    if model in _BROWSER_MODELS:
        from agent import worker
        loop = asyncio.get_event_loop()

        print(f"🚀 Starting Playwright browser context…")
        await loop.run_in_executor(None, worker.start)

        print(f"🌐 Opening tab for {model} and injecting system context…")
        await loop.run_in_executor(None, lambda: worker.preload(model))
        print(f"✅ {model} ready — server accepting requests")

    yield   # ← server is live here

    # (graceful teardown can be added here in the future)


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title       = "ChatGPT Simulation API",
    description = "Multi-provider LLM agent with OpenAI-compatible REST API",
    version     = "2.0.0",
    lifespan    = lifespan,
)


# ── Helper: run sync generate() without blocking the event loop ──────────────

async def _generate_async(model: str, messages: list[dict], **kwargs) -> str:
    """Wrap the synchronous router.generate() in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: generate(model, messages, **kwargs),
    )


# ── /v1/chat/completions  (OpenAI-compatible) ─────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion.

    Accepts the standard OpenAI request format and returns an identical
    response schema so any OpenAI client library can talk to this server.

    Example curl:
        curl http://localhost:8000/v1/chat/completions \\
          -H "Content-Type: application/json" \\
          -d '{"model":"gpt-4","messages":[{"role":"user","content":"hi"}]}'
    """
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    kwargs   = {
        "max_tokens":  req.max_tokens,
        "temperature": req.temperature,
        "timeout":     req.timeout,
    }

    try:
        response_text = await _generate_async(req.model, messages, **kwargs)

    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    # ── Build OpenAI-schema response ──────────────────────────────────────
    return {
        "id":      f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object":  "chat.completion",
        "created": int(time.time()),
        "model":   req.model,
        "choices": [
            {
                "index":   0,
                "message": {
                    "role":    "assistant",
                    "content": response_text,
                },
                "finish_reason": "stop",
            }
        ],
        # Token counts are unavailable for browser/local providers
        "usage": {
            "prompt_tokens":     0,
            "completion_tokens": 0,
            "total_tokens":      0,
        },
    }


# ── /v1/models ────────────────────────────────────────────────────────────────

@app.get("/v1/models")
async def list_models():
    """
    Return the list of available model identifiers.
    Mirrors the structure of the OpenAI /v1/models endpoint.
    """
    model_ids = sorted(set(PROVIDER_MAP.keys()))
    return {
        "object": "list",
        "data": [
            {
                "id":       mid,
                "object":   "model",
                "created":  1_700_000_000,
                "owned_by": "local",
            }
            for mid in model_ids
        ],
    }


# ── /status  (health check) ───────────────────────────────────────────────────

@app.get("/status")
async def status():
    """
    Return the current state of the Playwright browser worker.
    Useful for health checks and readiness probes.
    """
    from agent import worker
    return worker.get_status()


# ── /message  (legacy backward-compat endpoint) ───────────────────────────────

@app.post("/message")
async def message(payload: LegacyMessageRequest):
    """
    Legacy single-message endpoint kept for backward compatibility with
    v1 clients that do not use the OpenAI-compatible format.

    Routes through cfg.default_model.
    """
    messages = [{"role": "user", "content": payload.text}]

    try:
        response_text = await _generate_async(
            cfg.default_model, messages, timeout=payload.timeout
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"response": response_text}
