import os
import json
import datetime
from typing import List, Dict, Any, Optional
from .schemas import GraphNode, GraphEdge, KnowledgeGraph, MemoryRecord

# Path to persistent storage
STATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "state"))
GRAPH_PATH = os.path.join(STATE_DIR, "graph.json")
MEMORY_PATH = os.path.join(STATE_DIR, "memory.json")
RUNS_PATH = os.path.join(STATE_DIR, "runs.json")

def ensure_state_dir():
    """Ensure that the state directory exists."""
    os.makedirs(STATE_DIR, exist_ok=True)

def load_graph() -> KnowledgeGraph:
    """Load the persistent knowledge graph from JSON."""
    ensure_state_dir()
    if not os.path.exists(GRAPH_PATH):
        return KnowledgeGraph(nodes={}, edges=[])
    
    try:
        with open(GRAPH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Reconstruct nodes and edges into Pydantic models
            nodes = {k: GraphNode.model_validate(v) for k, v in data.get("nodes", {}).items()}
            edges = [GraphEdge.model_validate(e) for e in data.get("edges", [])]
            return KnowledgeGraph(nodes=nodes, edges=edges)
    except Exception as e:
        print(f"Error loading graph, initializing empty: {e}")
        return KnowledgeGraph(nodes={}, edges=[])

def save_graph(graph: KnowledgeGraph):
    """Save the knowledge graph to JSON."""
    ensure_state_dir()
    try:
        data = {
            "nodes": {k: v.model_dump() for k, v in graph.nodes.items()},
            "edges": [e.model_dump() for e in graph.edges]
        }
        with open(GRAPH_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving graph: {e}")

def add_node(node: GraphNode):
    """Add a node to the global graph, merging duplicates cleanly."""
    graph = load_graph()
    node_id = node.id.lower().strip()
    
    if node_id in graph.nodes:
        existing = graph.nodes[node_id]
        # Merge attributes
        merged_attrs = {**existing.attributes, **node.attributes}
        # Merge source URLs
        merged_urls = list(set(existing.source_urls + node.source_urls))
        # Merge confidence (use max or weighted average)
        merged_confidence = max(existing.confidence, node.confidence)
        
        graph.nodes[node_id] = GraphNode(
            id=existing.id,
            type=existing.type,
            label=existing.label,
            attributes=merged_attrs,
            source_urls=merged_urls,
            confidence=merged_confidence,
            created_run_id=existing.created_run_id # preserve original creation source
        )
    else:
        # Save as new node
        graph.nodes[node_id] = node
        
    save_graph(graph)

def add_edge(edge: GraphEdge):
    """Add an edge to the global graph, merging duplicates cleanly."""
    graph = load_graph()
    
    # Check if edge already exists between source, target, and relation
    matching_edge = None
    for existing in graph.edges:
        if (existing.source.lower() == edge.source.lower() and 
            existing.target.lower() == edge.target.lower() and 
            existing.relation.lower() == edge.relation.lower()):
            matching_edge = existing
            break
            
    if matching_edge:
        # Merge evidence
        if edge.evidence not in matching_edge.evidence:
            matching_edge.evidence = f"{matching_edge.evidence} | {edge.evidence}"
        # Merge confidence
        matching_edge.confidence = max(matching_edge.confidence, edge.confidence)
    else:
        graph.edges.append(edge)
        
    save_graph(graph)

def load_memory() -> List[MemoryRecord]:
    """Load persistent memory records."""
    ensure_state_dir()
    if not os.path.exists(MEMORY_PATH):
        return []
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [MemoryRecord.model_validate(r) for r in data]
    except Exception as e:
        print(f"Error loading memory records: {e}")
        return []

def save_memory(records: List[MemoryRecord]):
    """Save persistent memory records."""
    ensure_state_dir()
    try:
        data = [r.model_dump() for r in records]
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving memory: {e}")

def record_run(run_id: str, query: str, extracted_facts: List[str], entities: List[str]):
    """Record a completed research run into durable memory."""
    records = load_memory()
    
    record = MemoryRecord(
        run_id=run_id,
        query=query,
        extracted_facts=extracted_facts,
        entities=entities,
        timestamp=datetime.datetime.utcnow().isoformat()
    )
    records.append(record)
    save_memory(records)
    
    # Save to runs log history
    save_run_history(record)

def save_run_history(record: MemoryRecord):
    """Saves a run record to runs.json log file."""
    ensure_state_dir()
    history = []
    if os.path.exists(RUNS_PATH):
        try:
            with open(RUNS_PATH, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            pass
            
    history.append(record.model_dump())
    try:
        with open(RUNS_PATH, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error writing run history: {e}")

def search_memory(query: str) -> List[Dict[str, Any]]:
    """
    Search durable memory records and the active graph for matching facts or entities.
    Returns matched facts and supporting context.
    """
    records = load_memory()
    graph = load_graph()
    
    matches = []
    query_words = set(query.lower().split())
    
    # 1. Search facts in run records
    for r in records:
        for fact in r.extracted_facts:
            fact_words = set(fact.lower().split())
            intersection = query_words.intersection(fact_words)
            if len(intersection) >= 2 or (len(query_words) == 1 and query.lower() in fact.lower()):
                matches.append({
                    "type": "fact",
                    "text": fact,
                    "evidence": f"Learned in run: '{r.query}'",
                    "timestamp": r.timestamp
                })
                
    # 2. Search graph nodes
    for node_id, node in graph.nodes.items():
        if query.lower() in node.label.lower() or query.lower() in node_id:
            attrs_str = ", ".join(f"{k}: {v}" for k, v in node.attributes.items())
            matches.append({
                "type": "entity",
                "text": f"{node.label} ({node.type}) - {attrs_str}",
                "evidence": f"Source: {', '.join(node.source_urls) if node.source_urls else 'Direct Graph Entry'}",
                "timestamp": datetime.datetime.utcnow().isoformat() # default active
            })
            
    return matches

def reset_state():
    """Wipe all persistent state databases (graph, memory, runs)."""
    ensure_state_dir()
    for path in [GRAPH_PATH, MEMORY_PATH, RUNS_PATH]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Error resetting path {path}: {e}")

async def extract_and_update_graph(query: str, tool_result_str: str, run_id: str) -> List[str]:
    """
    Calls the LLM Gateway Memory layer (auto_route="memory") to extract key entities (nodes),
    relationships (edges), and facts from the raw tool execution result.
    Updates the persistent graph database in real-time and returns the list of extracted facts.
    """
    import httpx
    GATEWAY_URL = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")
    
    system_prompt = (
        "You are the Memory & Graph Layer of the NeuroWeave Cognitive OS.\n"
        "Your task is to analyze raw evidence or search results retrieved by tool executions, "
        "and extract a structured JSON representation of:\n"
        "1. Nodes: key entities discovered (concepts, technologies, companies, people, articles, etc.). "
        "Each node MUST have a unique lowercase slug-style ID (e.g. 'fastapi', 'elon_musk'), a label, a type, "
        "attributes (key-value metadata), source_urls (list of supporting URLs), and a confidence score (0.0 to 1.0).\n"
        "2. Edges: relationships between nodes. Each edge MUST have source, target, relation (founded_by, created_by, "
        "related_to, supports, mentions, contradicts, derived_from, connected_to), evidence (direct excerpt), and confidence.\n"
        "3. Extracted Facts: a list of short, dense, plain-text facts (e.g., 'FastAPI was created by Sebastian Ramirez.') "
        "that summarize the core evidence found.\n"
        "Your output must be strictly valid JSON conforming exactly to the requested schema."
    )
    
    # Cap input text size to avoid bloating the prompt
    capped_result = tool_result_str[:8000]
    
    prompt = (
        f"RESEARCH QUERY: \"{query}\"\n\n"
        f"RAW EVIDENCE TO PROCESS:\n"
        f"-------------------------\n"
        f"{capped_result}\n"
        f"-------------------------\n\n"
        "Analyze the raw evidence and return a JSON object in this exact format:\n"
        "{\n"
        "  \"nodes\": [\n"
        "    {\n"
        "      \"id\": \"normalized_slug_id\",\n"
        "      \"type\": \"person|company|concept|technology|website|article|event|fact\",\n"
        "      \"label\": \"Human Readable Title\",\n"
        "      \"attributes\": { \"key1\": \"value1\" },\n"
        "      \"source_urls\": [\"https://example.com\"],\n"
        "      \"confidence\": 0.95\n"
        "    }\n"
        "  ],\n"
        "  \"edges\": [\n"
        "    {\n"
        "      \"source\": \"source_node_slug_id\",\n"
        "      \"target\": \"target_node_slug_id\",\n"
        "      \"relation\": \"founded_by|created_by|related_to|supports|mentions|contradicts|derived_from|connected_to\",\n"
        "      \"evidence\": \"Supporting excerpt from text\",\n"
        "      \"confidence\": 0.90\n"
        "    }\n"
        "  ],\n"
        "  \"extracted_facts\": [\n"
        "    \"Short factual sentence extracted from this evidence.\"\n"
        "  ]\n"
        "}"
    )
    
    try:
        body = {
            "prompt": prompt,
            "system": system_prompt,
            "max_tokens": 2048,
            "temperature": 0.1,
            "auto_route": "memory",
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(f"{GATEWAY_URL}/v1/chat", json=body)
            r.raise_for_status()
            res = r.json()
            
        data = json.loads(res["text"])
        
        # 1. Process and save extracted nodes
        for node_dict in data.get("nodes", []):
            try:
                # Sanitize ID
                node_dict["id"] = node_dict["id"].lower().replace(" ", "_").strip()
                node_dict["created_run_id"] = run_id
                node = GraphNode.model_validate(node_dict)
                add_node(node)
            except Exception as ex:
                print(f"Failed to validate node {node_dict}: {ex}")
                
        # 2. Process and save extracted edges
        for edge_dict in data.get("edges", []):
            try:
                edge_dict["source"] = edge_dict["source"].lower().replace(" ", "_").strip()
                edge_dict["target"] = edge_dict["target"].lower().replace(" ", "_").strip()
                edge_dict["created_run_id"] = run_id
                edge = GraphEdge.model_validate(edge_dict)
                add_edge(edge)
            except Exception as ex:
                print(f"Failed to validate edge {edge_dict}: {ex}")
                
        return data.get("extracted_facts", [])
        
    except Exception as e:
        print(f"Memory Layer Graph Extraction Error: {e}")
        return []
