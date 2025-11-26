import asyncio
import json
import re
from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

import os

# ---------- Load prompts and metadata ----------

BASE_DIR = Path(__file__).resolve().parent

def load_prompt() -> str:
    """
    Load the long planner prompt from prompts/query_planner.txt
    """
    prompt_path = BASE_DIR / "prompts" / "query_planner.txt"
    return prompt_path.read_text(encoding="utf-8")

def load_metadata_text() -> str:
    """
    Dynamically load all metadata Markdown files in the metadata/ directory.
    Returns a unified text blob to pass to the planner agent.
    """
    metadata_dir = BASE_DIR / "data" / "metadata"
    parts = []

    # Load every .md file in alphabetical order
    for md_file in sorted(metadata_dir.glob("*.md")):
        header = f"\n# {md_file.stem.replace('_', ' ').upper()}\n"
        parts.append(header)
        parts.append(md_file.read_text(encoding="utf-8"))
        parts.append("\n")

    return "\n".join(parts)

# ---------- Build the planner agent ----------

def build_planner_agent() -> LlmAgent:
    """
    Construct the Query Planner LlmAgent.
    Its text output will be stored in session.state["query_plan"].
    """
    instruction = load_prompt()

    planner_agent = LlmAgent(
        name="QueryPlanner",
        model="gemini-2.5-flash",        
        instruction=instruction,
        output_key="query_plan",         # saves raw text response into state["query_plan"]
    )
    return planner_agent

def extract_json(raw_text: str) -> str:
    """
    Try to extract a JSON object from an LLM response.

    Handles cases like:
      ```json
      { ... }
      ```
    or extra prose around a JSON block.
    """
    text = raw_text.strip()

    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        # remove starting ```... line
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        # remove trailing ``` if present
        if "```" in text:
            text = text[: text.rfind("```")]
        text = text.strip()

    # Try to find the first '{' and last '}' and extract that chunk
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    # Fallback: return the whole thing
    return text

# ---------- Call the planner ----------

async def run_planner(
    question: str,
    session_service,
    app_name: str,
    user_id: str,
    session_id: str,
) -> dict:
    """
    Call the planner agent and return the parsed query_plan JSON.
    Assumes the session already exists (created by the orchestrator).
    """
    planner_agent = build_planner_agent()

    runner = Runner(
        agent=planner_agent,
        app_name=app_name,
        session_service=session_service,
    )

    metadata_text = load_metadata_text()
    user_payload = (
        f"USER QUESTION:\n{question}\n\n"
        "METADATA (SCHEMAS & GEOGRAPHY):\n"
        f"{metadata_text}\n"
    )
    content = Content(parts=[Part(text=user_payload)])

    raw_text = None
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response():
            raw_text = event.content.parts[0].text

    if raw_text is None:
        raise RuntimeError("Planner did not return a response")

    plan = json.loads(extract_json(raw_text))

    # Also store parsed plan into session.state for downstream agents
    session = await session_service.get_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    session.state["query_plan_json"] = plan


    return plan