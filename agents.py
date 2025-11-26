import pandas as pd
import io
import os
import csv
from datetime import datetime
import time
import json
import contextlib
from pathlib import Path

from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
from config import gpt_model, gpt_model_adv, OUTPUT_TOKEN_LIMIT

from tools import execute_python_code
from helper import make_json_safe, log_token_usage

BASE_DIR = Path(__file__).resolve().parent

try:
    api_key
except NameError:
    api_key = None

if api_key:
    client = OpenAI(api_key= api_key)
else:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = f"logs/token_usage.csv"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_python_code",
            "description": (
                "Execute Python code inside the agent's Python environment. "
                "The environment persists across tool calls within the same agent run. "
                "The code must be valid Python and must include all needed imports, "
                "data loading, and variable definitions. "
                "If producing a final result, store it in a variable named `result_df` "
                "and optional metadata in `result_meta`."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": (
                            "The full Python script to execute. "
                            "Must be self-contained, including imports and data loading. "
                            "The final output should be assigned to `result_df`, "
                            "with optional metadata assigned to `result_meta`."
                        ),
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": (
                            "If true, the code execution output is printed to the console. "
                            "If false, it is captured silently and returned through stdout."
                        ),
                        "default": False,
                    },
                },
                "required": ["code"],
            },
        },
    }
]

def call_tool(tool_name: str, **kwargs) -> dict:
    if tool_name == "execute_python_code":
        return execute_python_code(**kwargs)
    return {"success": False, "error": f"Unknown tool: {tool_name}"}

def load_prompt(file_name: str) -> str:
    prompt_path = BASE_DIR / "prompts" / file_name
    return prompt_path.read_text(encoding="utf-8")

da_agent_prompt = load_prompt("da_agent.txt")
ds_agent_prompt = load_prompt("ds_agent.txt")
orchestrator_prompt = load_prompt("orchestrator_agent.txt")
summarize_prompt = load_prompt("summarize_agent.txt")

def build_focus(original_question: str = "", focus:str|None = None) -> str:
    if focus is None:
        return(
            "USER QUESTION:\n"
            f"{original_question}\n\n"
        )

    return (
        "USER QUESTION:\n"
        f"{original_question}\n\n"
        "FOCUS:\n"
        f"{focus}\n\n"
    )

def describe_env(env: dict, env_meta: dict = {}) -> str:
    """
    Create a short textual description of what's in `env`
    (just to help the model understand what objects exist).
    """
    import pandas as pd

    lines = []
    for name, obj in env.items():
        if isinstance(obj, pd.DataFrame):
            lines.append(
                f"- {name}: DataFrame with shape {obj.shape} and columns {list(obj.columns[:10])}"
            )
            if name in env_meta:
                lines.append(f"  Metadata: {env_meta[name]}")
    return "\n".join(lines)

def run_python_da_agent(user_prompt: str, metadata_text:str = "", max_steps: int = 3, verbose: bool = False) -> str:
    """
    user_prompt: the user's question or task.
    metadata_text: text describing available data files and their schemas.
    max_steps: max number of LLM ↔ tool iterations.
    Returns: 
    {
        "dataframe": pd.DataFrame or None,
        "metadata": dict,
        "stdout": str,
        "error": str or None
        }
    """
    messages = [
        {"role": "system", "content": da_agent_prompt},
        {"role": "system", "content": metadata_text},
        {"role": "user", "content": user_prompt},
    ]

    EXEC_ENV = {}

    last_stdout = ""
    last_error = None

    df = None
    meta = {}


    for step in range(max_steps):
        if verbose:
            print(f"\n--- Step {step + 1} ---")
            print("Message  before LLM call:", messages[-1])
        
        # Call model
        resp = client.chat.completions.create(
            model=gpt_model,   
            messages=messages,
            tools=TOOLS,
        )
        if resp.usage is not None:
            log_token_usage(
                agent_name = "DA agent",
                model = gpt_model,
                usage = resp.usage,
                LOG_PATH=LOG_PATH
            )

        msg = resp.choices[0].message
        if verbose:
            print("\n[LLM RESPONSE]")
            if msg.tool_calls:
                print("Tool calls:")
                for tc in msg.tool_calls:
                    print(f"- {tc.function.name}({tc.function.arguments})")

        if not msg.tool_calls:
            return {
                "dataframe": None,
                "metadata": {},
                "stdout": msg.content or "",
                "error": "Model did not call any tool; no code was executed.",
            }

        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })

        # Execute each requested tool
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = json.loads(tc.function.arguments)
            
            if tool_name == "execute_python_code":
                args['env'] = EXEC_ENV
            result = call_tool(tool_name, **args)

            # Update debug tracking
            last_stdout = result.get("stdout", "") or last_stdout
            if not result.get("success", False):
                last_error = result.get("error")

            # Add tool result back into the conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

            # If this was a successful code execution, check for result_df 
            if tool_name == "execute_python_code" and result.get("success", False): 
                # Pull result_df and result_meta from the execution environment
                if verbose:
                    print("\n[TOOL OUTPUT]")
                    print("Stdout:", result.get("stdout", ""))
                    print("Error:", result.get("error", "")) 
                df = EXEC_ENV.get("result_df") 
                meta = EXEC_ENV.get("result_meta", {})
            
            if df is not None: 
                return { 
                    "dataframe": df, 
                    "metadata": meta if isinstance(meta, dict) else {}, 
                    "stdout": result.get("stdout", ""), 
                    "error": None, }
            

    # If we hit max_steps without a plain answer
    return {
        "dataframe": None,
        "metadata": {},
        "stdout": last_stdout,
        "error": last_error or f"Reached maximum steps ({max_steps}) without producing result_df.",
    }

def run_data_scientist_agent(
    user_prompt: str,
    env: dict,
    metadata_text: str = "",
    env_meta: dict = {},
    max_steps: int = 3,
    verbose: bool = False) -> dict:
    """
    Run the data scientist agent with:
      - env: runtime data objects
      - metadata_text: long-form textual metadata
      - env_meta: structured metadata dict for objects in env
      - returns final answer + list of plots + tool logs

    Returns:
        {
          "answer": str,
          "figures": list[str],
          "dataframe": pd.DataFrame or None,
          "metadata": dict,
          "tool_calls": list[dict],
          "last_tool_output": dict
        }
    """

    user_content = (
        f"USER QUESTION:\n{user_prompt}\n\n"
        f"AVAILABLE OBJECTS IN env:\n{describe_env(env = env, env_meta = env_meta)}\n\n"
    )

    if metadata_text:
        user_content += f"ADDITIONAL LONG-FORM METADATA:\n{metadata_text}\n"

    messages = [
        {"role": "system", "content": ds_agent_prompt},
        {"role": "user", "content": user_content},
    ]

    last_tool_output = None
    tool_calls_log = []
    all_figures = []

    for step in range(max_steps):
        if verbose:
            print(f"\n--- Data Scientist Agent: Step {step + 1} ---")

        resp = client.chat.completions.create(
            model=gpt_model,
            messages=messages,
            tools=TOOLS,
        )

        if resp.usage is not None:
            log_token_usage(
                agent_name = "DS agent",
                model = gpt_model,
                usage = resp.usage,
                LOG_PATH=LOG_PATH
            )

        choice = resp.choices[0]
        message = choice.message

        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": message.tool_calls,
            }
        )

        if message.tool_calls:
            for tool_call in message.tool_calls:
                if verbose:
                    print(f"\nTool call: {tool_call.function.name} with args {tool_call.function.arguments}")
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if func_name == "execute_python_code":
                    code = args["code"]

                    tool_output = execute_python_code(env = env, code = code, verbose = False)
                    last_tool_output = tool_output

                    tool_calls_log.append({
                        "step": step + 1,
                        "tool_call_id": tool_call.id,
                        "code": code,
                        "output": tool_output,
                    })

                    # Collect figures
                    all_figures.extend(tool_output.get("figures", []))
                    safe_output = make_json_safe(tool_output)

                    # Feed result back to model
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": func_name,
                            "content": json.dumps(safe_output),
                        }
                    )
            continue

        final_answer = message.content or ""
        try:
            result_df = env.get("result_df") 
            result_meta = env.get("result_meta")
        except:
            result_df = pd.DataFrame()
            result_meta = {}

        return {
            "answer": final_answer,
            "dataframe": result_df,
            "metadata": result_meta,
            "figures": all_figures,
            "tool_calls": tool_calls_log,
            "last_tool_output": last_tool_output,
        }

    # ---- If max steps reached ----
    return {
        "answer": "The agent reached the maximum number of steps without producing a final answer.",
        "tool_calls": tool_calls_log,
        "last_tool_output": last_tool_output,
    }

def run_orchestrator_agent(user_prompt: str, metadata_text: str) -> dict:
    """
    Call the orchestrator agent to produce a JSON plan with DA/DS prompts.

    Returns a Python dict with keys:
      - requires_clarification (bool)
      - clarification_question (str or None)
      - plan (list of steps, possibly empty)
    """

    user_payload = (
        f"{user_prompt}\n\n"
        f"METADATA: \n {metadata_text} \n"
    )

    messages = [
        {"role": "system", "content": orchestrator_prompt},
        {"role": "user", "content": user_payload},
    ]

    resp = client.chat.completions.create(
        model=gpt_model_adv,
        messages=messages,
    )

    if resp.usage is not None:
        log_token_usage(
            agent_name = "Orchestrator agent",
            model = gpt_model_adv,
            usage = resp.usage,
            LOG_PATH=LOG_PATH
        )

    raw_content = resp.choices[0].message.content or ""
    try:
        plan_dict = json.loads(raw_content)
    except json.JSONDecodeError:
        raise ValueError(f"Orchestrator agent returned invalid JSON: {raw_content}")
    return plan_dict

def run_summarize_agent(ds_report: dict, user_prompt: str = "",  metadata_text:str = "", verbose: bool = False) -> str:
    """
    Call an agent to summarize the findings from the data scientist report into bullet points.

    Parameters
    ----------
    user_prompt : str
        A free-form instruction that typically embeds:
        - the original user question, and
        - any extra focus for this summary (e.g., audience, metrics).
    ds_report : dict
        Dict of the form { "ds_step_1": answer_1, "ds_step_2": answer_2, ... },
        where each value is a string produced by the Data Scientist Agent.
    metadata_text : str, optional
        Long-form metadata about the data and variables (e.g. schemas, definitions).
    """
    
    ds_report_str = json.dumps(ds_report, indent = 2, ensure_ascii=False)

    user_content = (
        f"{user_prompt}\n\n"
        f"Data Scientist Report(ds_report_dict):\n{ds_report_str}\n\n"
    )

    if metadata_text:
        user_content += f"Additional METADATA:\n{metadata_text}\n"

    messages = [
        {"role": "system", "content": summarize_prompt},
        {"role": "user", "content":user_content}
    ]

    resp = client.chat.completions.create(
        model = gpt_model_adv,
        messages = messages,
        max_completion_tokens = OUTPUT_TOKEN_LIMIT
    )

    if resp.usage is not None:
        log_token_usage(
            agent_name = "Summarize agent",
            model = gpt_model,
            usage = resp.usage,
            LOG_PATH=LOG_PATH
        )

    raw_content = resp.choices[0].message.content.strip() or ""
    if verbose:
        print(f"Key Findings \n {raw_content}")

    return raw_content

def run_all_agents(
    original_prompt: str,
    metadata_text: str,
    focus: str|None = None,
    max_steps: int = 100,
    verbose: bool = False
) -> dict:
    """
    Run the full pipeline: Orchestrator -> DA/DS agents as per plan.
    Returns a dict with final results and reports from each step.
    """

    user_prompt = build_focus(original_question=original_prompt, focus= focus)

    orchestrator_output = run_orchestrator_agent(
        user_prompt=user_prompt,
        metadata_text=metadata_text
    )

    plan = orchestrator_output.get("plan", [])

    if len(plan) >= max_steps:
        raise ValueError(f"Orchestrator plan has {len(plan)} steps, exceeding max_steps={max_steps}.")
    elif len(plan) == 0:
        raise ValueError("Orchestrator plan is empty; cannot proceed.")

    if verbose:
        print(f"Orchestrator plan:\n{plan}\n")

    if orchestrator_output['requires_clarification']:
        results = {
            "type": "clarification",
            "question": orchestrator_output['clarification_question']
        }
        return results

    shared_env = {}
    shared_meta = {}
    ds_report = {}
    all_figures = []

    for step in plan:
        step_id = step['step_id']
        goal = step['goal']
        da_prompt = step['da_prompt']
        ds_prompt = step['ds_prompt']
        depends_on = step['depends_on']

        if verbose:
            print(f"\n---Executing Step {step_id}: {goal} ---\n")

        if da_prompt is not None:
            if verbose:
                print(f"[DA] Running DA step {step_id} with prompt:\n{da_prompt}\n")

            output = run_python_da_agent(
                user_prompt=da_prompt,
                metadata_text=metadata_text,
                verbose=verbose,
            )

        if ds_prompt is not None:
            if verbose:
                print(f"[DS] Running DS step {step_id} with prompt:\n{ds_prompt}\n")
                print(f"[DS] Depends on: {depends_on}")

            ds_env = {}
            ds_meta = {}
            for dep in depends_on:
                try:
                    ds_env[f"df_{dep}"] = shared_env[f"df_{dep}"]
                    ds_meta[f"df_{dep}"] = shared_meta[f"df_{dep}"]
                except: 
                    pass
            output = run_data_scientist_agent(
                user_prompt=ds_prompt,
                env=ds_env,
                env_meta=ds_meta,
                max_steps = 5,
                verbose=verbose,
            )
            if verbose:
                print(f"[DS] Output of DS step {step_id}:\n{output.get('answer')}\n")

            ds_report[f"ds_step_{step_id}"] = output.get("answer")
            all_figures.extend(output.get("figures",[]))
        
        try:
            shared_env[f"df_{step_id}"] = output.get("dataframe")
            shared_meta[f"df_{step_id}"] = output.get("metadata")
        except:
            pass

    summary_text = run_summarize_agent(ds_report=ds_report, user_prompt=user_prompt, verbose = verbose)

    results = {
        "summary": summary_text,
        "stat_df": shared_env,
        "stat_metadata": shared_meta,
        "report": ds_report,
        "figures": all_figures,
    }

    return results

