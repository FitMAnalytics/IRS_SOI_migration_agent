from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
import time
import io
import contextlib
import sys
from typing import Any, Dict, List
import pandas as pd

'''def load_metadata_text(fname: str) -> str:
    """
    Load a single metadata Markdown file from metadata/ directory.

    Args:
        fname: filename (e.g., "soi_immigall_schema.md").

    Returns:
        The text content of that metadata file.
    """
    metadata_path = BASE_DIR / "data" / "metadata" / fname

    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    return metadata_path.read_text(encoding="utf-8")'''

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


# load datasets function, not needed anymore
def load_datasets(datasets: List[Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
    """
    Load all datasets into a mapping alias -> DataFrame.
    Each dataset dict is expected to have keys: name, alias, source, path.
    """
    dfs: Dict[str, pd.DataFrame] = {}
    for ds in datasets:
        alias = ds.get("alias")
        path = ds.get("path")
        source = ds.get("source", "local_file")
        if source != "local_file":
            raise ValueError(f"Unsupported dataset source '{source}' for alias '{alias}'")
        if not alias:
            raise ValueError("Each dataset must have an 'alias'.")
        if not path:
            raise ValueError(f"Dataset '{alias}' is missing 'path'.")
        dfs[alias] = pd.read_csv(path)
    return dfs

import json
from matplotlib.figure import Figure

def make_json_safe(obj):
    """
    Recursively convert objects to a JSON-serializable form.
    We especially want to strip out matplotlib Figures.
    """
    if isinstance(obj, Figure):
        # We don't send the actual figure via JSON; just a placeholder
        return "<matplotlib.figure.Figure>"
    elif isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(v) for v in obj]
    # You can add more cases here for numpy types, DataFrames, etc., if needed.
    return obj

import csv
import os
from datetime import datetime


def log_token_usage(agent_name: str, model: str, usage, LOG_PATH: str, extra_info: dict | None = None):
    """
    Append a row of token usage stats to a CSV log file.
    - agent_name: 'orchestrator', 'da_agent', 'ds_agent', etc.
    - model: model name used for this call
    - usage: resp.usage object from OpenAI
    - extra_info: optional dict, e.g. {'user_question': '...', 'step_id': 3}
    """
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    row = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "agent_name": agent_name,
        "model": model,
        "total_tokens": getattr(usage, "total_tokens", None),
    }

    if extra_info:
        for k, v in extra_info.items():
            row[k] = v

    file_exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
