import os
import json
import httpx
from .schemas import PerceptionOutput, QueryIntent

def _gateway_url() -> str:
    """Runtime lookup so main.py startup event can override LLM_GATEWAY_V3_URL."""
    return os.getenv("LLM_GATEWAY_V3_URL", "http://localhost:8101")

async def analyze_query_perception(query: str) -> PerceptionOutput:
    """
    Analyzes the user query using the Perception cognitive layer (routed to TINY/LARGE).
    Extracts intent, seed entities, complexity, and suggests tools.
    """
    system_prompt = (
        "You are the Perception Layer of the NeuroWeave Cognitive OS.\n"
        "Your task is to analyze user queries and output a structured JSON object representing "
        "the query intent, extracted seed entities, estimated complexity (1 to 5), suggested tools, "
        "and an initial reasoning roadmap.\n"
        "Ensure your output is strictly valid JSON matching the specified schema."
    )
    
    prompt = (
        f"Analyze the following user query:\n"
        f"\"{query}\"\n\n"
        "Return a JSON object conforming exactly to this structure:\n"
        "{\n"
        "  \"query\": \"original query text\",\n"
        "  \"intent\": {\n"
        "    \"intent_type\": \"factual|research|fact_check|synthesis\",\n"
        "    \"primary_domain\": \"tech|business|history|general\"\n"
        "  },\n"
        "  \"extracted_entities\": [\"entity1\", \"entity2\"],\n"
        "  \"estimated_complexity\": 3,\n"
        "  \"suggested_tools\": [\"web_search\", \"fetch_url\", \"get_time\", \"read_file\"],\n"
        "  \"initial_reasoning_path\": \"Step-by-step hypothesis and search plan\"\n"
        "}"
    )
    
    try:
        body = {
            "prompt": prompt,
            "system": system_prompt,
            "max_tokens": 1024,
            "temperature": 0.1,
            "auto_route": "perception",
            "response_format": {"type": "json_object"}
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{_gateway_url()}/v1/chat", json=body)
            r.raise_for_status()
            res = r.json()
            
        # Parse text into Pydantic model
        parsed_data = json.loads(res["text"])
        return PerceptionOutput.model_validate(parsed_data)
        
    except Exception as e:
        print(f"Perception Layer Error: {e}, falling back to rule-based parser.")
        # Graceful fallback to avoid failure
        return PerceptionOutput(
            query=query,
            intent=QueryIntent(intent_type="research", primary_domain="general"),
            extracted_entities=[query],
            estimated_complexity=3,
            suggested_tools=["web_search", "fetch_url"],
            initial_reasoning_path="Rule-based fallback initiated due to gateway timeout/error."
        )
