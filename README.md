# Migration Multi-Agent Analysis System

A lightweight multi-agent system for analyzing IRS SOI interstate migration data (2012–2022).
It converts natural-language questions into automated data extraction, analysis, visualization, and summaries using OpenAI models.

## Live Demo (Streamlit)

https://cjrupupup.streamlit.app/

## Architecture (Short Overview)

```
User Query
    ↓
Orchestrator Agent
    - Interprets question
    - Plans analysis from multiple angles (rates, counts, AGI)
    - Creates multiple Data Analyst (DA) tasks + one Data Scientist (DS) task

DA Agents (Data Analyst)
    - Execute Python code
    - Pull & aggregate inmigall parquet files
    - One metric per DA step
    - Output: result_df + result_meta

DS Agent (Data Scientist)
    - Combines DA outputs
    - Performs trend analysis & plotting
    - Output: analysis_df + charts

Summary Agent
    - Produces a concise human-readable answer
```

Agents rely on Markdown metadata (inmigall_schema.md, soi_derived_metrics.md, state_fips_reference.md, etc.) to correctly interpret user intent.

## Installation

1. Clone the repo:
```
git clone https://github.com/<your-user>/migration-agent.git
cd migration-agent
```

2. Create a `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

3. Install dependencies:
```
pip install -r requirements.txt
```

## Local Usage Example

```python
from agents import run_all_agents
from metadata import load_metadata_text

metadata = load_metadata_text()

question = "Summarize migration trends for Texas from 2018 to 2022."

result = run_all_agents(
    user_prompt=question,
    metadata_text=metadata,
    verbose=False,
)

print(result["summary"])
```

## Project Structure (Short)

```
prompts/             # agent system prompts
metadata/            # SOI schema, derived metrics, FIPS, regions
agents.py            # orchestrator, DA, DS, summary agents
run_all_agents.py    # main entry point
data/                # inmigall parquet files
```

## License

MIT License
