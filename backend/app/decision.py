import os
import json
import httpx
from .schemas import DecisionInput, DecisionOutput, NextAction, ToolAction

def _gateway_url() -> str:
    """Runtime lookup so main.py startup event can override LLM_GATEWAY_V3_URL."""
    return os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")

async def plan_next_decision(input_state: DecisionInput) -> DecisionOutput:
    """
    Evaluates current research state, gathered facts, and the graph summary to decide the next best action.
    Uses the Decision cognitive layer (routed to TINY/LARGE/HUGE).
    """
    system_prompt = (
        "You are the Decision Layer of the NeuroWeave Cognitive OS.\n"
        "Your task is to review the user's research query, perception analysis, current execution iteration, "
        "history of previous tool calls and outcomes, currently accumulated facts, and the state of the knowledge graph.\n"
        "You must decide the NEXT logical action: either execute a tool (like web_search, fetch_url, get_time, read_file) "
        "or FINALIZE with a final answer if sufficient evidence is gathered or confidence is high.\n"
        "Avoid redundant searches and tool repetitions. Set confidence_score to indicate how close we are to a complete solution (0.0 to 1.0).\n"
        "Ensure your output is strictly valid JSON conforming to the requested schema."
    )
    
    # Format action history nicely for the LLM
    history_lines = []
    for idx, act in enumerate(input_state.action_history):
        history_lines.append(
            f"Step {idx+1}: Called '{act.get('tool_name')}' with args {act.get('arguments')}\n"
            f"Result: {act.get('output')[:1000]}..."
        )
    history_str = "\n\n".join(history_lines) if history_lines else "No actions executed yet."
    
    prompt = (
        f"USER QUERY: \"{input_state.query}\"\n\n"
        f"PERCEPTION PLAN: {input_state.perception.initial_reasoning_path}\n"
        f"SUGGESTED SEED ENTITIES: {', '.join(input_state.perception.extracted_entities)}\n\n"
        f"ITERATION: {input_state.iteration} / {input_state.max_iterations}\n\n"
        f"ACTION HISTORY LOGS:\n{history_str}\n\n"
        f"ACCUMULATED FACTS:\n" + "\n".join(f"- {f}" for f in input_state.current_facts) + "\n\n"
        f"CURRENT PERSISTENT KNOWLEDGE GRAPH SUMMARY:\n{input_state.graph_summary}\n\n"
        "DETERMINE THE NEXT ACTION. Return a JSON object in this exact format:\n"
        "{\n"
        "  \"thought\": \"your step-by-step reasoning thought process\",\n"
        "  \"next_action\": {\n"
        "    \"action_type\": \"tool|finalize\",\n"
        "    \"next_tool_call\": { \n"
        "       \"name\": \"web_search|fetch_url|get_time|read_file|create_file|update_file|list_dir\",\n"
        "       \"arguments\": { ... }\n"
        "    }\n"
        "  },\n"
        "  \"confidence_score\": 0.85,\n"
        "  \"stop_reason\": null\n"
        "}\n"
        "NOTE: If action_type is 'finalize', set next_tool_call to null."
    )
    
    try:
        body = {
            "prompt": prompt,
            "system": system_prompt,
            "max_tokens": 1500,
            "temperature": 0.1,
            "auto_route": "decision",
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(f"{_gateway_url()}/v1/chat", json=body)
            r.raise_for_status()
            res = r.json()
            
        parsed_data = json.loads(res["text"])
        
        # Guard against LLM outputting null/missing tool call fields in the dict
        next_act = parsed_data.get("next_action", {})
        if next_act.get("action_type") == "tool" and not next_act.get("next_tool_call"):
            parsed_data["next_action"]["action_type"] = "finalize"
            parsed_data["stop_reason"] = "Forced finalize: Tool action decided but tool_call was null."
            
        return DecisionOutput.model_validate(parsed_data)
        
    except Exception as e:
        print(f"Decision Layer Error: {e}, falling back to finalize.")
        # Graceful fallback to avoid infinity loops
        return DecisionOutput(
            thought=f"Exception in decision logic: {str(e)}. Gracefully finalizing to prevent system freeze.",
            next_action=NextAction(action_type="finalize"),
            confidence_score=0.5,
            stop_reason="Exception fallback to finalize"
        )
