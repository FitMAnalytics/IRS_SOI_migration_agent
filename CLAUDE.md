# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a multi-agent system for analyzing IRS SOI (Statistics of Income) interstate migration data (2012-2022). The system converts natural-language questions into automated data extraction, analysis, visualization, and summaries using OpenAI models.

**Live Demo**: https://cjrupupup.streamlit.app/

## Setup and Development

### Installation
```bash
pip install -r requirements.txt
```

### Environment Configuration
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your_api_key_here
```

### Running the Application

**Local Python usage**:
```python
from agents import run_all_agents
from helper import load_metadata_text

metadata = load_metadata_text()
prompt = "Analyze the interstate migration pattern of Texas, from 2012 to 2022."
focus = "Focus on different behavior between low income classes (annual gross income less than $50,000)."
results = run_all_agents(original_prompt=prompt, focus=focus, metadata_text=metadata, verbose=False)

print(results["summary"])
```

**Streamlit web interface**:
```bash
streamlit run app.py
```

## Architecture

### Multi-Agent Pipeline

The system follows a strict orchestrator → executor pattern with four specialized agents:

1. **Orchestrator Agent** (`orchestrator_agent.txt`)
   - Interprets user questions and optional FOCUS directives
   - Creates a JSON execution plan with ordered steps
   - Each step specifies `da_prompt` (Data Analyst), `ds_prompt` (Data Scientist), and dependencies
   - Uses advanced model (`gpt_model_adv` in config.py)
   - **Never executes code or pulls data directly**

2. **Data Analyst (DA) Agents** (`da_agent.txt`)
   - Execute Python code via `execute_python_code` tool
   - Pull and aggregate parquet files from `data/raw/` or `data/processed/`
   - Each agent handles one atomic metric/geography task
   - Output: `result_df` (DataFrame) + `result_meta` (dict with column descriptions and `_summary`)
   - Persistent execution environment within single agent run

3. **Data Scientist (DS) Agent** (`ds_agent.txt`)
   - Combines outputs from multiple DA agents
   - Performs trend analysis, comparisons, and visualizations
   - Uses only DA outputs (never re-queries raw data)
   - Output: analysis text + matplotlib figures + `result_df`

4. **Summary Agent** (`summarize_agent.txt`)
   - Produces concise human-readable final answer
   - Synthesizes all DS agent outputs
   - Uses advanced model (`gpt_model_adv`)

### Execution Flow

```
User Query + optional FOCUS
    ↓
Orchestrator Agent (creates plan)
    ↓
For each step in plan:
    DA Agent (if da_prompt) → result_df + result_meta
    ↓
    DS Agent (if ds_prompt, using DA outputs) → analysis + figures
    ↓
Summary Agent (synthesizes all DS outputs)
    ↓
Final results: {summary, stat_df, stat_metadata, report, figures}
```

### Key Design Principles

- **Metadata-driven**: All agents rely on Markdown files in `data/metadata/` to understand data schemas, derived metrics, and geography mappings
- **Atomic DA tasks**: Each DA step handles one geography, clear time range, minimal grouping
- **Rate-based comparisons**: Geographic comparisons MUST use rates (e.g., `inflow_n1 / total_n1`), never raw counts
- **FOCUS directive**: When provided, takes precedence over default multi-angle analysis
- **Tool calling pattern**: Agents use OpenAI function calling with `execute_python_code` tool

## Core Files

### Agent Implementation
- `agents.py`: All agent runner functions (`run_orchestrator_agent`, `run_python_da_agent`, `run_data_scientist_agent`, `run_summarize_agent`, `run_all_agents`)
- `prompts/`: System prompts for each agent (orchestrator, DA, DS, summarize)
- `tools.py`: `execute_python_code` function with persistent environment and figure capture
- `helper.py`: `load_metadata_text()`, `make_json_safe()`, `log_token_usage()`
- `config.py`: Model configuration (`gpt_model`, `gpt_model_adv`, `OUTPUT_TOKEN_LIMIT`)

### Data and Metadata
- `data/raw/`: Raw IRS SOI inmigall CSV files
- `data/processed/`: Processed migration data (e.g., `soi_migration_long.csv`)
- `data/metadata/`: Schema definitions and reference tables
  - `soi_inmigall_schema.md`: Primary data schema
  - `soi_derived_metrics.md`: Rate calculations and derived metrics
  - `state_fips_reference.md`: State codes and region mappings
  - `cpi_u_reference.md`: CPI-U deflators for inflation adjustment
  - `index_agent.md`: Metadata index
- `data/reference/`: Lookup tables (e.g., `statefips_dict.csv`)

### Application
- `app.py`: Streamlit entry point
- `stpages.py`: Streamlit page components (API key verification, agent interaction)
- `main.py`: Alternative entry point (appears minimal/unused)

## Important Implementation Notes

### Agent Communication Protocol

All agents use OpenAI tool calling. The `execute_python_code` tool:
- Accepts `code` (string) and optional `verbose` (bool)
- Maintains persistent execution environment (`env` dict) within agent run
- Automatically injects `pd`, `np`, `plt`, `sns` into environment
- Captures stdout, stderr, and matplotlib figures
- Returns dict with `success`, `stdout`, `stderr`, `figures`, `execution_time_seconds`

### Data Schema Key Points

**Migration classes** (`class` column):
- `total`: All filers with prior-year address in this state
- `nonmig`: No address change
- `outflow`: Moved out to another state
- `inflow`: Moved in from another state
- `samest`: Moved within same state

**AGI stubs** (`agi_stub`):
- 0: All AGI classes combined
- 1-7: Income brackets from <$10k to $200k+

**Age classes** (`age_class`):
- 0: All ages
- 1-6: Age brackets from 0-25 to 65+

**Key metrics**:
- `n1`: Number of tax returns
- `n2`: Number of individuals
- `y1_agi`, `y2_agi`: AGI in first/second year (thousands of nominal dollars)

### Derived Metrics Pattern

Always compute rates for geographic comparisons:
```python
inflow_rate = inflow_n1 / total_n1
outflow_rate = outflow_n1 / total_n1
net_migration_rate = (inflow_n1 - outflow_n1) / total_n1
inflow_FAGI_rate = inflow_y2_agi / total_y2_agi
net_FAGI_rate = (inflow_y2_agi - outflow_y2_agi) / total_y2_agi
```

### Token Usage Logging

All agent calls log token usage to `logs/token_usage.csv` via `log_token_usage()` function. This includes:
- timestamp
- agent_name
- model
- total_tokens

## Testing

- `agents_testing.ipynb`: Main testing notebook for agent pipeline
- `generate_fips_dict.ipynb`: FIPS code generation utilities
- `archived_codes/`: Old implementations (planner_agent.py, executor_tool.py, executor_agent_testing.ipynb)

## Model Configuration

Current models are configured in `config.py`:
- `gpt_model = "gpt-5-mini"`: For DA and DS agents
- `gpt_model_adv = "gpt-5.1"`: For Orchestrator and Summary agents
- `OUTPUT_TOKEN_LIMIT = 2000`: For summary agent

When modifying model selection, update these constants rather than hardcoding model names.

## Metadata System

The `load_metadata_text()` function in `helper.py` dynamically loads all `.md` files from `data/metadata/` in alphabetical order, creating a unified text blob that gets passed to agents. This ensures agents have complete context about:
- Available data fields and their definitions
- Geography hierarchies (state, region, division)
- Derived metric formulas
- Data coverage and caveats

When adding new data sources or derived metrics, create corresponding `.md` files in `data/metadata/`.
