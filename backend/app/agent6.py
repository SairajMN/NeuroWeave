import os
import uuid
import json
import httpx
import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable
from .schemas import (
    UserQuery,
    PerceptionOutput,
    DecisionInput,
    DecisionOutput,
    NextAction,
    ToolAction,
    ToolResult,
    FinalAnswer,
    AnswerEvidence
)
from .perception import analyze_query_perception
from .decision import plan_next_decision
from .action import execute_mcp_tool
from .memory import (
    load_graph,
    load_memory,
    search_memory,
    record_run,
    extract_and_update_graph
)

GATEWAY_URL = os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")

class TelemetryLogger:
    """Helper class to trigger callbacks during cognitive transitions."""
    def __init__(self, callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None):
        self.callback = callback

    async def log(self, phase: str, payload: Dict[str, Any]):
        if self.callback:
            try:
                await self.callback(phase, payload)
            except Exception as e:
                print(f"Telemetry Callback Error ({phase}): {e}")
        else:
            print(f"[{phase.upper()}] {json.dumps(payload, indent=2)[:500]}...")

async def generate_final_answer(
    query: str,
    perception: PerceptionOutput,
    current_facts: List[str],
    graph_summary: str,
    reasoning_path: List[str]
) -> FinalAnswer:
    """
    Renders the final synthesis and answer markdown using LLM Gateway.
    Links answers back to extracted knowledge graph nodes and web sources.
    """
    system_prompt = (
        "You are the Synthesis & Final Answer Layer of the NeuroWeave Cognitive OS.\n"
        "Your task is to compile all the facts, evidence, and knowledge graph entities gathered "
        "and produce a comprehensive, futuristic, beautifully structured markdown answer.\n"
        "You must cite supporting evidence by linking statements back to graph nodes or source URLs.\n"
        "Ensure your output is strictly valid JSON conforming exactly to the requested schema."
    )

    prompt = (
        f"RESEARCH QUERY: \"{query}\"\n\n"
        f"PERCEPTION ANALYSIS:\n"
        f"- Roadmap: {perception.initial_reasoning_path}\n"
        f"- Complexity: {perception.estimated_complexity}\n\n"
        f"ACCUMULATED FACTS:\n" + "\n".join(f"- {f}" for f in current_facts) + "\n\n"
        f"CURRENT PERSISTENT KNOWLEDGE GRAPH SUMMARY:\n{graph_summary}\n\n"
        f"COGNITIVE STEPS TAKEN:\n" + "\n".join(f"- {step}" for step in reasoning_path) + "\n\n"
        "Formulate your final synthesis. Return a JSON object in this exact format:\n"
        "{\n"
        "  \"query\": \"original user query\",\n"
        "  \"answer\": \"Detailed, professional, sci-fi premium styled markdown answer with headers, bold points, and clean syntax.\",\n"
        "  \"confidence\": 0.95,\n"
        "  \"evidence\": [\n"
        "    {\n"
        "      \"fact\": \"Exact fact statement\",\n"
        "      \"source_node\": \"graph_node_slug_id_if_applicable\",\n"
        "      \"source_url\": \"https://example.com/source_url_if_applicable\"\n"
        "    }\n"
        "  ],\n"
        "  \"reasoning_path\": [\"Description of cognitive steps taken\"]\n"
        "}"
    )

    try:
        body = {
            "prompt": prompt,
            "system": system_prompt,
            "max_tokens": 3000,
            "temperature": 0.2,
            "auto_route": "decision",  # Routing final answer synthesis to decision-level power
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(f"{GATEWAY_URL}/v1/chat", json=body)
            r.raise_for_status()
            res = r.json()

        parsed_data = json.loads(res["text"])
        return FinalAnswer.model_validate(parsed_data)

    except Exception as e:
        print(f"Final Answer Generation Error: {e}, using fallback generator.")
        # Graceful fallback answer
        summary_facts = "\n".join(f"- {f}" for f in current_facts)
        return FinalAnswer(
            query=query,
            answer=(
                f"# Research Results for: {query}\n\n"
                f"We gathered the following facts during our research:\n\n{summary_facts}\n\n"
                f"*Note: Fallback synthesis triggered due to an LLM rendering exception.*"
            ),
            confidence=0.6,
            evidence=[AnswerEvidence(fact=f, source_node=None, source_url=None) for f in current_facts],
            reasoning_path=reasoning_path + [f"Fallback activated: {str(e)}"]
        )

async def run_autonomous_research(
    query: str,
    run_id: Optional[str] = None,
    telemetry_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
) -> FinalAnswer:
    """
    Main autonomous agent loop implementing the 4 cognitive layers.
    Capped at a maximum of 6 reasoning cycles.
    """
    if not run_id:
        run_id = f"run_{uuid.uuid4().hex[:8]}"

    logger = TelemetryLogger(telemetry_callback)

    # -------------------------------------------------------------
    # PHASE 1: PERCEPTION LAYER
    # -------------------------------------------------------------
    await logger.log("perception_start", {"query": query, "run_id": run_id})
    perception = await analyze_query_perception(query)
    await logger.log("perception_end", perception.model_dump())

    # -------------------------------------------------------------
    # MEMORY RETRIEVAL (Durable memory injection)
    # -------------------------------------------------------------
    await logger.log("memory_recall_start", {"query": query})
    recalled_memories = search_memory(query)
    recalled_facts = []
    recalled_entities = []
    
    for item in recalled_memories:
        if item["type"] == "fact":
            recalled_facts.append(item["text"])
        elif item["type"] == "entity":
            recalled_entities.append(item["text"])

    await logger.log("memory_recall_end", {
        "recalled_facts": recalled_facts,
        "recalled_entities": recalled_entities
    })

    # Initialize loop state
    max_iterations = 6
    iteration = 1
    action_history = []
    
    # Pre-populate facts with recalled historical data
    current_facts = recalled_facts.copy()
    reasoning_path = [f"Initialized research with seed entities: {perception.extracted_entities}"]
    if recalled_facts:
        reasoning_path.append(f"Injected {len(recalled_facts)} relevant facts from prior runs into working memory.")

    # -------------------------------------------------------------
    # COGNITIVE REASONING LOOP (DECISION -> ACTION -> MEMORY)
    # -------------------------------------------------------------
    while iteration <= max_iterations:
        await logger.log("iteration_start", {"iteration": iteration})

        # Generate persistent graph summary for LLM visibility
        graph = load_graph()
        graph_summary_nodes = [f"{n.label} ({n.type}): {n.attributes}" for n in graph.nodes.values()]
        graph_summary_edges = [f"{e.source} -> {e.relation} -> {e.target}" for e in graph.edges]
        graph_summary = (
            f"Nodes ({len(graph_summary_nodes)}):\n" + "\n".join(graph_summary_nodes[:25]) + "\n\n"
            f"Edges ({len(graph_summary_edges)}):\n" + "\n".join(graph_summary_edges[:25])
        )

        decision_input = DecisionInput(
            query=query,
            perception=perception,
            iteration=iteration,
            max_iterations=max_iterations,
            action_history=action_history,
            current_facts=current_facts,
            graph_summary=graph_summary
        )

        # Execute DECISION cognitive layer
        await logger.log("decision_start", {"iteration": iteration})
        decision = await plan_next_decision(decision_input)
        await logger.log("decision_end", {
            "iteration": iteration,
            "decision": decision.model_dump()
        })

        reasoning_path.append(f"Iteration {iteration}: {decision.thought}")

        # Check if finalized or reached max depth
        if decision.next_action.action_type == "finalize" or iteration == max_iterations:
            await logger.log("loop_converged", {
                "iteration": iteration,
                "reason": decision.stop_reason or "Max cognitive depth reached."
            })
            break

        # Check for tool details
        tool_call = decision.next_action.next_tool_call
        if not tool_call:
            await logger.log("loop_converged", {
                "iteration": iteration,
                "reason": "Decision indicated tool but no tool details provided."
            })
            break

        # Prevent exact tool duplication loop
        already_called = any(
            h.get("tool_name") == tool_call.name and h.get("arguments") == tool_call.arguments
            for h in action_history
        )
        if already_called:
            await logger.log("loop_warning", {
                "warning": f"Detected potential infinite loop calling '{tool_call.name}' with same args. finalising."
            })
            break

        # -------------------------------------------------------------
        # PHASE 2: ACTION LAYER (MCP Execution)
        # -------------------------------------------------------------
        await logger.log("action_start", {
            "iteration": iteration,
            "tool_call": tool_call.model_dump()
        })
        tool_result = await execute_mcp_tool(tool_call)
        await logger.log("action_end", {
            "iteration": iteration,
            "result": {
                "tool_name": tool_result.tool_name,
                "success": tool_result.success,
                "output_preview": tool_result.output[:1000] + "..." if len(tool_result.output) > 1000 else tool_result.output,
                "error": tool_result.error
            }
        })

        # Save to history log
        action_history.append({
            "tool_name": tool_result.tool_name,
            "arguments": tool_call.arguments,
            "output": tool_result.output,
            "success": tool_result.success
        })

        # -------------------------------------------------------------
        # PHASE 3: MEMORY & GRAPH LAYER (Semantic extraction & merge)
        # -------------------------------------------------------------
        if tool_result.success and tool_result.output.strip():
            await logger.log("memory_update_start", {"iteration": iteration})
            new_facts = await extract_and_update_graph(query, tool_result.output, run_id)
            
            # Deduplicate and add newly found facts
            added_count = 0
            for fact in new_facts:
                if fact not in current_facts:
                    current_facts.append(fact)
                    added_count += 1
                    
            await logger.log("memory_update_end", {
                "iteration": iteration,
                "new_facts_extracted": new_facts,
                "added_to_working_memory": added_count
            })

        iteration += 1

    # -------------------------------------------------------------
    # PHASE 4: FINAL ANSWER LAYER & RECORD RUN
    # -------------------------------------------------------------
    await logger.log("synthesis_start", {"facts_count": len(current_facts)})
    final_graph = load_graph()
    graph_summary_nodes = [f"{n.label} ({n.type}): {n.attributes}" for n in final_graph.nodes.values()]
    graph_summary_edges = [f"{e.source} -> {e.relation} -> {e.target}" for e in final_graph.edges]
    graph_summary = (
        f"Nodes ({len(graph_summary_nodes)}):\n" + "\n".join(graph_summary_nodes) + "\n\n"
        f"Edges ({len(graph_summary_edges)}):\n" + "\n".join(graph_summary_edges)
    )

    final_answer = await generate_final_answer(
        query=query,
        perception=perception,
        current_facts=current_facts,
        graph_summary=graph_summary,
        reasoning_path=reasoning_path
    )
    
    # Durable record of this run
    record_run(
        run_id=run_id,
        query=query,
        extracted_facts=current_facts,
        entities=list(final_graph.nodes.keys())
    )

    await logger.log("synthesis_end", final_answer.model_dump())
    return final_answer
