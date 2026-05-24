"""NeuroWeave automated test suite.
Tests Pydantic validation, graph merge logic, memory search, and state recovery.
Integration tests require llm_gatewayV3 running on port 8101.
"""
import os
import sys
import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure backend is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas import (
    UserQuery,
    PerceptionOutput,
    QueryIntent,
    ToolAction,
    ToolResult,
    NextAction,
    DecisionInput,
    DecisionOutput,
    GraphNode,
    GraphEdge,
    KnowledgeGraph,
    MemoryRecord,
    AnswerEvidence,
    FinalAnswer,
)
from app.memory import (
    load_graph,
    save_graph,
    add_node,
    add_edge,
    load_memory,
    save_memory,
    search_memory,
    record_run,
    reset_state,
)

# =====================================================================
# SCHEMA / PYDANTIC VALIDATION TESTS
# =====================================================================

class TestSchemaValidation:
    def test_valid_perception_output(self):
        data = {
            "query": "What is FastAPI?",
            "intent": {"intent_type": "factual", "primary_domain": "tech"},
            "extracted_entities": ["FastAPI", "Python"],
            "estimated_complexity": 2,
            "suggested_tools": ["web_search"],
            "initial_reasoning_path": "Search for FastAPI definition and creator."
        }
        p = PerceptionOutput.model_validate(data)
        assert p.query == "What is FastAPI?"
        assert p.estimated_complexity == 2

    def test_invalid_complexity_out_of_range(self):
        data = {
            "query": "test",
            "intent": {"intent_type": "research", "primary_domain": "general"},
            "extracted_entities": [],
            "estimated_complexity": 6,  # must be 1-5
            "suggested_tools": [],
            "initial_reasoning_path": "path"
        }
        with pytest.raises(ValidationError):
            PerceptionOutput.model_validate(data)

    def test_confidence_range_enforced(self):
        with pytest.raises(ValidationError):
            DecisionOutput(
                thought="test",
                next_action=NextAction(action_type="finalize"),
                confidence_score=1.5,  # must be 0.0-1.0
            )

    def test_tool_action_roundtrip(self):
        ta = ToolAction(name="web_search", arguments={"query": "test"})
        result = ToolResult(tool_name="web_search", success=True, output="test output")
        assert result.tool_name == "web_search"
        assert result.success is True

    def test_graph_node_defaults(self):
        node = GraphNode(
            id="test_node",
            type="concept",
            label="Test Node",
            created_run_id="run_1"
        )
        assert node.confidence == 1.0
        assert node.source_urls == []
        assert node.attributes == {}

    def test_graph_edge_validation(self):
        edge = GraphEdge(
            source="node_a",
            target="node_b",
            relation="related_to",
            evidence="They are related.",
            created_run_id="run_1"
        )
        assert edge.source == "node_a"
        assert edge.relation == "related_to"
        assert edge.confidence == 1.0

    def test_final_answer_evidence_optional_fields(self):
        ev = AnswerEvidence(fact="Some fact")
        assert ev.fact == "Some fact"
        assert ev.source_node is None
        assert ev.source_url is None

    def test_memory_record_timestamp(self):
        from datetime import datetime
        r = MemoryRecord(
            run_id="run_test",
            query="test",
            extracted_facts=["fact1"],
            entities=["e1"],
            timestamp=datetime.utcnow().isoformat()
        )
        assert r.run_id == "run_test"


# =====================================================================
# GRAPH MERGE LOGIC TESTS
# =====================================================================

class TestGraphMerge:
    @pytest.fixture(autouse=True)
    def isolate_state(self):
        """Redirect graph/memory paths to temp dir for each test."""
        original_state = os.environ.get("_NW_TEST_STATE")
        self.tmp_dir = tempfile.mkdtemp(prefix="nw_test_")
        
        # Monkey-patch state paths
        import app.memory as mem_mod
        self._orig_state_dir = mem_mod.STATE_DIR
        self._orig_graph_path = mem_mod.GRAPH_PATH
        self._orig_memory_path = mem_mod.MEMORY_PATH
        self._orig_runs_path = mem_mod.RUNS_PATH
        
        mem_mod.STATE_DIR = self.tmp_dir
        mem_mod.GRAPH_PATH = os.path.join(self.tmp_dir, "graph.json")
        mem_mod.MEMORY_PATH = os.path.join(self.tmp_dir, "memory.json")
        mem_mod.RUNS_PATH = os.path.join(self.tmp_dir, "runs.json")
        
        yield
        
        # Restore original paths
        mem_mod.STATE_DIR = self._orig_state_dir
        mem_mod.GRAPH_PATH = self._orig_graph_path
        mem_mod.MEMORY_PATH = self._orig_memory_path
        mem_mod.RUNS_PATH = self._orig_runs_path

    def test_add_and_load_node(self):
        node = GraphNode(
            id="fastapi",
            type="technology",
            label="FastAPI",
            attributes={"python_version": "3.11"},
            source_urls=["https://fastapi.tiangolo.com"],
            confidence=0.95,
            created_run_id="run_1"
        )
        add_node(node)
        
        graph = load_graph()
        assert "fastapi" in graph.nodes
        assert graph.nodes["fastapi"].label == "FastAPI"
        assert graph.nodes["fastapi"].confidence == 0.95

    def test_node_duplicate_merge_confidence(self):
        n1 = GraphNode(
            id="fastapi", type="technology", label="FastAPI",
            attributes={"version": "0.100"}, source_urls=["url1"],
            confidence=0.8, created_run_id="run_1"
        )
        n2 = GraphNode(
            id="fastapi", type="technology", label="FastAPI",
            attributes={"version": "0.110"}, source_urls=["url2"],
            confidence=0.95, created_run_id="run_2"
        )
        add_node(n1)
        add_node(n2)
        
        graph = load_graph()
        node = graph.nodes["fastapi"]
        # Confidence should be max of both
        assert node.confidence == 0.95
        # URLs should be merged
        assert "url1" in node.source_urls
        assert "url2" in node.source_urls
        # Created run should preserve original
        assert node.created_run_id == "run_1"

    def test_edge_deduplication(self):
        e1 = GraphEdge(
            source="fastapi", target="sebastian_ramirez",
            relation="created_by", evidence="FastAPI created by SR.",
            confidence=0.9, created_run_id="run_1"
        )
        e2 = GraphEdge(
            source="fastapi", target="sebastian_ramirez",
            relation="created_by", evidence="Confirmed: SR is creator.",
            confidence=0.95, created_run_id="run_2"
        )
        add_edge(e1)
        add_edge(e2)
        
        graph = load_graph()
        assert len(graph.edges) == 1
        merged = graph.edges[0]
        # Evidence should be concatenated
        assert "FastAPI created by SR." in merged.evidence
        assert "Confirmed" in merged.evidence
        # Confidence should be max
        assert merged.confidence == 0.95

    def test_multiple_edges_different_relations(self):
        add_edge(GraphEdge(source="a", target="b", relation="related_to",
                           evidence="link", created_run_id="r1"))
        add_edge(GraphEdge(source="a", target="b", relation="supports",
                           evidence="supports", created_run_id="r1"))
        
        graph = load_graph()
        assert len(graph.edges) == 2


# =====================================================================
# MEMORY SEARCH TESTS
# =====================================================================

class TestMemorySearch:
    @pytest.fixture(autouse=True)
    def isolate_state(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="nw_test_")
        import app.memory as mem_mod
        self._orig_graph_path = mem_mod.GRAPH_PATH
        self._orig_memory_path = mem_mod.MEMORY_PATH
        self._orig_runs_path = mem_mod.RUNS_PATH
        self._orig_state_dir = mem_mod.STATE_DIR
        
        mem_mod.STATE_DIR = self.tmp_dir
        mem_mod.GRAPH_PATH = os.path.join(self.tmp_dir, "graph.json")
        mem_mod.MEMORY_PATH = os.path.join(self.tmp_dir, "memory.json")
        mem_mod.RUNS_PATH = os.path.join(self.tmp_dir, "runs.json")
        
        yield
        
        mem_mod.STATE_DIR = self._orig_state_dir
        mem_mod.GRAPH_PATH = self._orig_graph_path
        mem_mod.MEMORY_PATH = self._orig_memory_path
        mem_mod.RUNS_PATH = self._orig_runs_path

    def test_search_memory_by_keyword(self):
        record_run(
            run_id="run_test",
            query="What is FastAPI?",
            extracted_facts=["FastAPI is a modern web framework for Python."],
            entities=["fastapi"]
        )
        
        results = search_memory("FastAPI framework")
        assert len(results) > 0
        facts = [r for r in results if r["type"] == "fact"]
        assert any("FastAPI" in f["text"] for f in facts)

    def test_search_memory_no_match(self):
        record_run(
            run_id="run_no_match",
            query="About cats",
            extracted_facts=["Cats are furry animals."],
            entities=["cats"]
        )
        results = search_memory("quantum computing")
        # Should still return something because graph node might be found,
        # but no facts should match 'quantum computing'
        facts = [r for r in results if r["type"] == "fact"]
        quantum_matches = [f for f in facts if "quantum" in f["text"].lower()]
        assert len(quantum_matches) == 0

    def test_cross_run_memory_persistence(self):
        # First run
        record_run("r1", "Python frameworks",
                   ["Python Flask is a microframework.", "Python Django is full-stack."],
                   ["flask", "django"])
        # Second run
        record_run("r2", "Python web",
                   ["Python FastAPI is async."],
                   ["fastapi"])
        
        results = search_memory("Python")
        assert len(results) >= 3  # at least 3 facts across both runs


# =====================================================================
# STATE RECOVERY & RESET TESTS
# =====================================================================

class TestStateRecovery:
    @pytest.fixture(autouse=True)
    def isolate_state(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="nw_test_")
        import app.memory as mem_mod
        self._orig_graph_path = mem_mod.GRAPH_PATH
        self._orig_memory_path = mem_mod.MEMORY_PATH
        self._orig_runs_path = mem_mod.RUNS_PATH
        self._orig_state_dir = mem_mod.STATE_DIR
        
        mem_mod.STATE_DIR = self.tmp_dir
        mem_mod.GRAPH_PATH = os.path.join(self.tmp_dir, "graph.json")
        mem_mod.MEMORY_PATH = os.path.join(self.tmp_dir, "memory.json")
        mem_mod.RUNS_PATH = os.path.join(self.tmp_dir, "runs.json")
        
        yield
        
        mem_mod.STATE_DIR = self._orig_state_dir
        mem_mod.GRAPH_PATH = self._orig_graph_path
        mem_mod.MEMORY_PATH = self._orig_memory_path
        mem_mod.RUNS_PATH = self._orig_runs_path

    def test_empty_state_returns_valid_objects(self):
        graph = load_graph()
        assert isinstance(graph, KnowledgeGraph)
        assert graph.nodes == {}
        assert graph.edges == []
        
        mem = load_memory()
        assert mem == []

    def test_save_and_reload_graph_integrity(self):
        graph = KnowledgeGraph(
            nodes={
                "node1": GraphNode(id="node1", type="concept", label="Node One",
                                   created_run_id="r1"),
                "node2": GraphNode(id="node2", type="person", label="Node Two",
                                   created_run_id="r1"),
            },
            edges=[
                GraphEdge(source="node1", target="node2", relation="related_to",
                          evidence="They relate.", created_run_id="r1")
            ]
        )
        save_graph(graph)
        
        loaded = load_graph()
        assert len(loaded.nodes) == 2
        assert len(loaded.edges) == 1
        assert loaded.nodes["node1"].label == "Node One"
        assert loaded.nodes["node2"].id == "node2"

    def test_reset_state_clears_all(self):
        # Populate state
        add_node(GraphNode(id="test", type="concept", label="Test",
                           created_run_id="r1"))
        record_run("r1", "test query", ["fact1"], ["test"])
        
        reset_state()
        
        graph = load_graph()
        assert graph.nodes == {}
        assert graph.edges == []
        
        mem = load_memory()
        assert mem == []

    def test_run_history_accumulates(self):
        record_run("r1", "query1", ["fact1"], ["e1"])
        record_run("r2", "query2", ["fact2", "fact3"], ["e2", "e3"])
        
        mem = load_memory()
        assert len(mem) == 2
        assert mem[0].run_id == "r1"
        assert len(mem[1].extracted_facts) == 2


# =====================================================================
# RUN IF STANDALONE
# =====================================================================

if __name__ == "__main__":
    pytest.main(["-v", __file__])