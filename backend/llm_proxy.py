"""
NeuroWeave LLM Proxy - Lightweight gateway replacement for llm_gatewayV3.
Runs on port 8101, routes requests to OpenRouter/Gemini using .env API keys.
Implements the /v1/chat endpoint expected by the NeuroWeave cognitive layers.
"""
import os
import json
import httpx
import logging
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("llm_proxy")

app = FastAPI(title="NeuroWeave LLM Proxy", version="1.0.0")

# ── API Keys ──────────────────────────────────────────────────────────
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY", "")
MERCURY_KEY = os.getenv("ROUTER_MERCURY_API_KEY", "")
MERCURY_MODEL = os.getenv("ROUTER_MERCURY_MODEL", "mercury-2")

# Provider base URLs
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_BASE = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

# Route → model mapping
ROUTE_MODELS = {
    "perception": "google/gemini-2.0-flash-001",
    "decision": "openai/gpt-4o-mini",
    "memory": "google/gemini-2.0-flash-001",
}

# Fallback if a route isn't mapped
DEFAULT_MODEL = "openai/gpt-4o-mini"


class ChatRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    max_tokens: int = Field(default=1024, ge=64, le=4096)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    auto_route: Optional[str] = None
    response_format: Optional[dict] = None


async def call_openrouter(req: ChatRequest) -> str:
    """Send request to OpenRouter API."""
    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "NeuroWeave",
    }

    model = ROUTE_MODELS.get(req.auto_route or "", DEFAULT_MODEL)

    body = {
        "model": model,
        "messages": messages,
        "max_tokens": req.max_tokens,
        "temperature": req.temperature,
    }

    if req.response_format and req.response_format.get("type") == "json_object":
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(OPENROUTER_BASE, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()

    content = data["choices"][0]["message"]["content"]
    log.info(f"OpenRouter [{model}] → {len(content)} chars")
    return content


async def call_gemini(req: ChatRequest) -> str:
    """Fallback: send request to Google Gemini API."""
    if not GEMINI_KEY:
        raise ValueError("No Gemini API key available")

    parts = [{"text": req.prompt}]
    if req.system:
        parts.insert(0, {"text": f"[System Instruction]\n{req.system}"})

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": req.max_tokens,
            "temperature": req.temperature,
        }
    }

    if req.response_format and req.response_format.get("type") == "json_object":
        body["generationConfig"]["responseMimeType"] = "application/json"

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(GEMINI_BASE, json=body)
        r.raise_for_status()
        data = r.json()

    content = data["candidates"][0]["content"]["parts"][0]["text"]
    log.info(f"Gemini → {len(content)} chars")
    return content


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "system": "NeuroWeave LLM Proxy",
        "openrouter": bool(OPENROUTER_KEY),
        "gemini": bool(GEMINI_KEY),
        "mercury": bool(MERCURY_KEY),
    }


@app.post("/v1/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint for NeuroWeave cognitive layers.
    Routes to OpenRouter, with Gemini as fallback.
    """
    errors = []

    # Try OpenRouter first
    if OPENROUTER_KEY:
        try:
            text = await call_openrouter(req)
            return {"text": text}
        except Exception as e:
            log.warning(f"OpenRouter failed: {e}")
            errors.append(f"OpenRouter: {str(e)}")

    # Fallback to Gemini
    if GEMINI_KEY:
        try:
            text = await call_gemini(req)
            return {"text": text}
        except Exception as e:
            log.warning(f"Gemini failed: {e}")
            errors.append(f"Gemini: {str(e)}")

    # All providers failed
    raise httpx.HTTPStatusError(
        f"All LLM providers failed: {'; '.join(errors)}",
        request=None,
        response=None,
    )


if __name__ == "__main__":
    import uvicorn
    log.info("Starting NeuroWeave LLM Proxy on port 8101...")
    log.info(f"  OpenRouter key: {'✓' if OPENROUTER_KEY else '✗'}")
    log.info(f"  Gemini key:     {'✓' if GEMINI_KEY else '✗'}")
    log.info(f"  Mercury key:    {'✓' if MERCURY_KEY else '✗'}")
    uvicorn.run(app, host="0.0.0.0", port=8101)