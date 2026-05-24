# NeuroWeave — Autonomous Knowledge Graph Cognitive OS

NeuroWeave is an autonomous knowledge graph reasoning engine that transforms web evidence into structured memory and reusable intelligence. Using perception, decision, action, and memory layers, the system continuously evolves its internal world model to improve reasoning accuracy and convergence efficiency.

## Architecture

```
                    ┌──────────────┐
                    │  FastAPI SSE │
                    │  Server :8000│
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌─────▼─────┐
    │Percept. │─────►│Decision │─────►│  Action   │
    │ Layer   │      │ Layer   │      │  (MCP)    │
    └─────────┘      └────┬────┘      └────┬──────┘
                          │                │
                     ┌────▼────┐      ┌────▼──────┐
                     │ Memory  │◄─────│ Tool Exec │
                     │& Graph  │      │(web, fetch,│
                     └────┬────┘      │ filesystem)│
                          │           └───────────┘
                     ┌────▼────┐
                     │  Final  │
                     │ Answer  │
                     └─────────┘
```

## Project Structure

```
NeuroWeave/
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI SSE server
│   │   ├── agent6.py       # Cognitive orchestrator
│   │   ├── schemas.py      # Pydantic v2 schemas
│   │   ├── perception.py   # Query analysis layer
│   │   ├── decision.py     # Reasoning & planning layer
│   │   ├── action.py       # MCP stdio client
│   │   ├── mcp_server.py   # Tool server (search, fetch, fs)
│   │   ├── memory.py       # Graph persistence & memory search
│   │   └── reset_state.py  # State wipe utility
│   ├── tests/
│   │   └── test_agent.py   # 19 automated tests
│   ├── pyproject.toml      # uv project config
│   └── .env                # API keys & gateway config
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Root layout
│   │   ├── types.ts        # TypeScript interfaces
│   │   ├── index.css       # Cinematic design system
│   │   ├── store/
│   │   │   └── useStore.ts # Zustand state + SSE API
│   │   └── components/
│   │       ├── TopologyBar.tsx         # Status bar with confidence gauge
│   │       ├── CognitiveStream.tsx     # HUD telemetry log
│   │       ├── GraphCanvas.tsx         # 3D force-directed graph
│   │       ├── QueryInputBar.tsx       # Input + action buttons
│   │       ├── FinalAnswerRenderer.tsx # Synthesis result panel
│   │       └── RunHistoryModal.tsx     # Past run explorer
│   ├── package.json
│   └── vite.config.ts
├── state/
│   ├── graph.json     # Persistent knowledge graph
│   ├── memory.json    # Cross-run durable memory
│   └── runs.json      # Run history log
└── README.md
```

## Prerequisites

- **Python 3.11+** with `uv` package manager
- **Node.js 20+** with `npm`
- **LLM Gateway V3** running on `http://localhost:8101`

## Quick Start

### 1. Start the LLM Gateway (port 8101)

```bash
# Ensure your gateway is running on port 8101
# Otherwise update LLM_GATEWAY_V3_URL in .env
```

### 2. Start the Backend

```bash
cd backend
uv sync
cp .env.example .env   # Edit with your API keys
uv run uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 4. Run Tests

```bash
cd backend
uv run pytest tests/test_agent.py -v
```

Expected output: **19 passed**

## Tavily AI Search Integration

The MCP server now includes two Tavily-powered search tools that the cognitive agent can use:

| Tool | Purpose |
|---|---|
| `tavily_search` | Structured search with AI-generated summary, titles, URLs, and content snippets |
| `tavily_search_context` | Deeper search with full raw content extraction for detailed analysis |

To enable Tavily:
1. Get an API key from [tavily.com](https://tavily.com)
2. Add it to `.env`: `TAVILY_API_KEY=tvly-your-key-here`

The existing DuckDuckGo `web_search` and `fetch_url` tools remain available as fallbacks.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/research` | POST (SSE) | Submit query, streams real-time telemetry |
| `/api/graph` | GET | Current knowledge graph (nodes + links) |
| `/api/memory` | GET | Durable memory records |
| `/api/history` | GET | Run history |
| `/api/reset` | POST | Wipe all persistent state |
| `/api/status` | GET | Health check |

## Cognitive Layers

1. **Perception** — Analyzes query intent, extracts seed entities, estimates complexity
2. **Decision** — Plans next action (tool call vs finalize), tracks budget of 6 iterations
3. **Action** — Executes MCP tools (web search, URL fetch, file operations)
4. **Memory & Graph** — Extracts entities/facts/relations, merges into persistent graph with confidence scoring

## Design System

- Deep graphite/black background (`#0A0A0C`)
- Neon cyan accents (`#00F0FF`), purple (`#9D4EDD`), green (`#00FF88`)
- Glassmorphism cards with fine border frames
- WebGL 3D force-directed graph with particle flow animations
- Real-time HUD telemetry with per-phase color coding

## License

MIT