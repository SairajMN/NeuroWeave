import os
import json
import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import httpx

# Load .env from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from .schemas import UserQuery
from .agent6 import run_autonomous_research
from .memory import load_graph, load_memory, reset_state, RUNS_PATH

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("neuroweave")

# ── FastAPI App ─────────────────────────────────────────────────────
app = FastAPI(title="NeuroWeave Cognitive OS API", version="1.0.0")

# Enable CORS for frontend VITE server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup Event ───────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    # Set the LLM gateway URL to point to ourselves (merged proxy runs on same server)
    port = os.getenv("PORT", "8000")
    os.environ["LLM_GATEWAY_V3_URL"] = f"http://0.0.0.0:{port}"
    log.info(f"LLM Gateway V3 URL set to http://0.0.0.0:{port}")
    log.info(f"  OpenRouter key: {'✓' if (os.getenv('OPENROUTER_API_KEY') or os.getenv('OPEN_ROUTER_API_KEY')) else '✗'}")
    log.info(f"  Gemini key:     {'✓' if (os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_AI_API_KEY')) else '✗'}")

# ── API Keys for LLM Proxy ──────────────────────────────────────────
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_API_KEY", "")
MERCURY_KEY = os.getenv("ROUTER_MERCURY_API_KEY", "")

# Provider base URLs
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"
GEMINI_BASE = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

# Route → model mapping
ROUTE_MODELS = {
    "perception": "google/gemini-2.0-flash-001",
    "decision": "openai/gpt-4o-mini",
    "memory": "google/gemini-2.0-flash-001",
}
DEFAULT_MODEL = "openai/gpt-4o-mini"


# ── LLM Proxy Models ────────────────────────────────────────────────
class ChatRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    max_tokens: int = Field(default=1024, ge=64, le=4096)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    auto_route: Optional[str] = None
    response_format: Optional[dict] = None


# ── LLM Provider Functions ──────────────────────────────────────────
async def call_openrouter(req: ChatRequest) -> str:
    """Send request to OpenRouter API."""
    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/NeuroWeave",
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


# ── LLM Proxy Endpoints (merged into main.py) ──────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "system": "NeuroWeave Cognitive OS API",
        "openrouter": bool(OPENROUTER_KEY),
        "gemini": bool(GEMINI_KEY),
        "mercury": bool(MERCURY_KEY),
    }


@app.post("/v1/chat")
async def chat(req: ChatRequest):
    """
    LLM Gateway endpoint for NeuroWeave cognitive layers.
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


# ── Research Request ────────────────────────────────────────────────
class ResearchRequest(BaseModel):
    query: str
    run_id: str = None

@app.get("/api/status")
async def get_status():
    return {"status": "online", "system": "NeuroWeave OS Substrate"}

@app.post("/api/research")
async def research_stream(req: ResearchRequest):
    """
    Spawns an autonomous research agent session and streams real-time
    telemetry events (Perception, Decision, Action, Memory) via Server-Sent Events (SSE).
    """
    query = req.query
    run_id = req.run_id

    async def event_generator():
        queue = asyncio.Queue()

        async def telemetry_cb(phase: str, payload: dict):
            await queue.put({"phase": phase, "payload": payload})

        # Start research agent execution loop in background
        task = asyncio.create_task(run_autonomous_research(query, run_id, telemetry_cb))

        def on_task_done(_task):
            pass  # signal handled below via task.done() + queue.empty()

        task.add_done_callback(on_task_done)

        while True:
            try:
                # Wait for queue items with a timeout; also check if task is done
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f"data: {json.dumps(event)}\n\n"
                queue.task_done()
            except asyncio.TimeoutError:
                # If task is finished and queue is empty, break
                if task.done() and queue.empty():
                    break
                # Send a heart-beat/keep-alive comment
                yield ": keep-alive\n\n"

        try:
            # Yield final synthetic outcome
            final_answer = await task
            yield f"data: {json.dumps({'phase': 'complete', 'payload': final_answer.model_dump()})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'phase': 'error', 'payload': {'message': str(e)}})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/graph")
async def get_graph():
    """
    Returns the accumulated knowledge graph mapped perfectly
    to the list formats required by D3 force-graph visualization.
    """
    graph = load_graph()
    
    nodes_list = []
    for nid, node in graph.nodes.items():
        nodes_list.append({
            "id": node.id,
            "type": node.type,
            "label": node.label,
            "attributes": node.attributes,
            "source_urls": node.source_urls,
            "confidence": node.confidence,
            "created_run_id": node.created_run_id
        })
        
    links_list = []
    for edge in graph.edges:
        links_list.append({
            "source": edge.source,
            "target": edge.target,
            "relation": edge.relation,
            "evidence": edge.evidence,
            "confidence": edge.confidence,
            "created_run_id": edge.created_run_id
        })

    return {
        "nodes": nodes_list,
        "links": links_list
    }

@app.get("/api/memory")
async def get_memory():
    """
    Returns lists of facts gathered in durable memories.
    """
    records = load_memory()
    return {"records": [r.model_dump() for r in records]}

@app.get("/api/history")
async def get_history():
    """
    Returns run-by-run logged history of the Agent's reasoning.
    """
    if not os.path.exists(RUNS_PATH):
        return {"history": []}
    try:
        with open(RUNS_PATH, "r", encoding="utf-8") as f:
            history = json.load(f)
            return {"history": history}
    except Exception:
        return {"history": []}

@app.post("/api/reset")
async def reset_agent_state():
    """
    Wipes persistent state files.
    """
    reset_state()
    return {"success": True, "message": "Global agent knowledge graph, runs history, and memory wiped successfully."}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    log.info(f"Starting NeuroWeave Cognitive OS API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)