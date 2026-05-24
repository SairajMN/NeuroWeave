from pydantic import BaseModel, Field
from typing import Any, Optional, List, Dict

# =====================================================================
# 1. Query & Perception Models
# =====================================================================

class UserQuery(BaseModel):
    query: str = Field(..., description="The raw natural language query from the user")
    run_id: Optional[str] = Field(None, description="Unique ID for this session/run")

class QueryIntent(BaseModel):
    intent_type: str = Field(..., description="Type of query: e.g., factual, research, fact_check, synthesis")
    primary_domain: str = Field(..., description="Main subject area, e.g., tech, business, history, general")

class PerceptionOutput(BaseModel):
    query: str = Field(..., description="The analyzed query")
    intent: QueryIntent = Field(..., description="Structured intent of the query")
    extracted_entities: List[str] = Field(default_factory=list, description="Seed entities extracted from the query")
    estimated_complexity: int = Field(..., ge=1, le=5, description="Complexity score from 1 (easy) to 5 (extremely deep)")
    suggested_tools: List[str] = Field(default_factory=list, description="MCP tools recommended for this research")
    initial_reasoning_path: str = Field(..., description="Starting hypothesis and research roadmap")

# =====================================================================
# 2. Action Models
# =====================================================================

class ToolAction(BaseModel):
    name: str = Field(..., description="The name of the MCP tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")

class ToolResult(BaseModel):
    tool_name: str = Field(..., description="Name of the tool that was executed")
    success: bool = Field(..., description="Whether the tool execution succeeded")
    output: str = Field(..., description="Raw or normalized text result from the tool")
    error: Optional[str] = Field(None, description="Error message if success is False")

class NextAction(BaseModel):
    action_type: str = Field(..., description="Either 'tool' to execute a tool or 'finalize' to generate the final answer")
    next_tool_call: Optional[ToolAction] = Field(None, description="The tool to call if action_type is 'tool'")

# =====================================================================
# 3. Decision Models
# =====================================================================

class DecisionInput(BaseModel):
    query: str = Field(..., description="The original user query")
    perception: PerceptionOutput = Field(..., description="The initial query perception analysis")
    iteration: int = Field(..., description="The current cognitive iteration index")
    max_iterations: int = Field(..., description="Maximum allowed iterations before hard stopping")
    action_history: List[Dict[str, Any]] = Field(default_factory=list, description="Logs of previous actions and results")
    current_facts: List[str] = Field(default_factory=list, description="Currently gathered facts in active memory")
    graph_summary: str = Field(..., description="Textual summary of current nodes/edges in the persistent graph")

class DecisionOutput(BaseModel):
    thought: str = Field(..., description="Detailed step-by-step reasoning thought process")
    next_action: NextAction = Field(..., description="The next action decided by the cognitive engine")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the current solution state (0.0 to 1.0)")
    stop_reason: Optional[str] = Field(None, description="Reason for stopping, if finalizing")

# =====================================================================
# 4. Memory & Graph Models
# =====================================================================

class GraphNode(BaseModel):
    id: str = Field(..., description="Unique normalized identifier (slug/lowercase)")
    type: str = Field(..., description="Node category: person, company, concept, technology, website, article, event, fact")
    label: str = Field(..., description="Human-readable title/label")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")
    source_urls: List[str] = Field(default_factory=list, description="URLs supporting this node")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence (0.0 to 1.0)")
    created_run_id: str = Field(..., description="The run ID in which this node was created")

class GraphEdge(BaseModel):
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    relation: str = Field(..., description="Relation: founded_by, created_by, related_to, supports, mentions, contradicts, derived_from, connected_to")
    evidence: str = Field(..., description="Sentence or excerpt supporting this relation")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Edge confidence score (0.0 to 1.0)")
    created_run_id: str = Field(..., description="The run ID in which this edge was created")

class MemoryRecord(BaseModel):
    run_id: str = Field(..., description="Unique execution run ID")
    query: str = Field(..., description="The query being researched")
    extracted_facts: List[str] = Field(default_factory=list, description="Facts extracted during this run")
    entities: List[str] = Field(default_factory=list, description="Entities processed during this run")
    timestamp: str = Field(..., description="ISO 8601 creation timestamp")

class KnowledgeGraph(BaseModel):
    nodes: Dict[str, GraphNode] = Field(default_factory=dict, description="Mapping of node ID to GraphNode")
    edges: List[GraphEdge] = Field(default_factory=list, description="List of all GraphEdges")

# =====================================================================
# 5. Final Output Models
# =====================================================================

class AnswerEvidence(BaseModel):
    fact: str = Field(..., description="The supporting fact statement")
    source_node: Optional[str] = Field(None, description="The graph node ID providing this fact")
    source_url: Optional[str] = Field(None, description="The web URL support if applicable")

class FinalAnswer(BaseModel):
    query: str = Field(..., description="The original query")
    answer: str = Field(..., description="Futuristic, comprehensive, beautifully written answer markdown")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall answer confidence score")
    evidence: List[AnswerEvidence] = Field(default_factory=list, description="List of structured supporting evidence items")
    reasoning_path: List[str] = Field(default_factory=list, description="Cognitive steps taken to reach this result")
