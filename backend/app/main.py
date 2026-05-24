import os
import json
import asyncio
from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .schemas import UserQuery
from .agent6 import run_autonomous_research
from .memory import load_graph, load_memory, reset_state, RUNS_PATH

app = FastAPI(title="NeuroWeave Cognitive OS API", version="1.0.0")

# Enable CORS for frontend VITE server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        while not task.done() or not queue.empty():
            try:
                # Retrieve logs with a short timeout to keep connection alive
                event = await asyncio.wait_for(queue.get(), timeout=0.5)
                yield f"data: {json.dumps(event)}\n\n"
                queue.task_done()
            except asyncio.TimeoutError:
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
