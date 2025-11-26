from __future__ import annotations
from typing import Any, Dict, List, Optional
import pandas as pd


ALLOWED_FILTER_OPS = {
    "in",
    "not_in",
    "between",
    "equals",
    "not_equals",
    "gt",
    "gte",
    "lt",
    "lte",
}

ALLOWED_AGGS = {"sum", "count", "mean", "avg"}


def _apply_filters(df: pd.DataFrame, filters: Optional[Dict[str, Dict[str, Any]]]) -> pd.DataFrame:
    """
    Apply top-level filters to a DataFrame.

    filters is a mapping: column -> {op: value, ...}
    Supported ops: in, not_in, between, equals, not_equals, gt, gte, lt, lte.
    """
    if not filters:
        return df

    result = df
    for col, cond in filters.items():
        for op, val in cond.items():
            if op not in ALLOWED_FILTER_OPS:
                raise ValueError(f"Unsupported filter op '{op}' for column '{col}'")

            if op == "in":
                result = result[result[col].isin(val)]
            elif op == "not_in":
                result = result[~result[col].isin(val)]
            elif op == "between":
                lo, hi = val
                result = result[(result[col] >= lo) & (result[col] <= hi)]
            elif op == "equals":
                result = result[result[col] == val]
            elif op == "not_equals":
                result = result[result[col] != val]
            elif op == "gt":
                result = result[result[col] > val]
            elif op == "gte":
                result = result[result[col] >= val]
            elif op == "lt":
                result = result[result[col] < val]
            elif op == "lte":
                result = result[result[col] <= val]
            else:
                # Should be unreachable because of ALLOWED_FILTER_OPS check
                raise ValueError(f"Unexpected filter op '{op}' for column '{col}'")

    return result


def _aggregate_metrics(
    df: pd.DataFrame,
    group_by: List[str],
    metrics: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    Compute metrics with optional per-metric filters, returning a DataFrame
    with columns: group_by + metric_names.
    """
    if not group_by:
        raise ValueError("execute_query_plan currently requires a non-empty group_by.")

    # Start with distinct group keys as the base result frame
    result = df[group_by].drop_duplicates().reset_index(drop=True)

    for metric in metrics:
        name = metric["name"]
        agg = str(metric["agg"]).lower()
        col = metric["column"]
        m_filter = metric.get("filter")

        if agg not in ALLOWED_AGGS:
            raise ValueError(f"Unsupported aggregation '{agg}' in metric '{name}'")

        # Map "avg" to pandas "mean"
        if agg == "avg":
            agg_func = "mean"
        else:
            agg_func = agg

        m_df = df

        # Apply metric-level filters (simple equality filters for now)
        if m_filter:
            for fcol, fval in m_filter.items():
                m_df = m_df[m_df[fcol] == fval]

        grouped = m_df.groupby(group_by, dropna=False)[col]
        agg_series = getattr(grouped, agg_func)()
        m_out = agg_series.reset_index().rename(columns={col: name})

        # Left join into the base result
        result = result.merge(m_out, on=group_by, how="left")

    return result


def _load_datasets(datasets: List[Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
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


def _apply_joins(
    dfs: Dict[str, pd.DataFrame],
    datasets: List[Dict[str, Any]],
    joins: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    Combine multiple datasets using the specified joins.

    Assumptions for now:
    - The first dataset in `datasets` is the "base".
    - Joins connect this base to other datasets (possibly in a chain).
    - Join spec:
        {
          "type": "inner" | "left" | "right" | "outer",
          "left_dataset": "m",
          "right_dataset": "s",
          "on": [
            {"left_column": "state", "right_column": "state"},
            ...
          ]
        }
    """
    if not datasets:
        raise ValueError("No datasets specified in plan.")

    # If only one dataset and no joins, just return that DataFrame
    if len(datasets) == 1 and not joins:
        base_alias = datasets[0]["alias"]
        return dfs[base_alias]

    if len(datasets) > 1 and not joins:
        raise ValueError("Multiple datasets provided but no joins specified.")

    # Start from the first dataset as the base
    base_alias = datasets[0]["alias"]
    if base_alias not in dfs:
        raise ValueError(f"Base dataset alias '{base_alias}' not found in loaded dataframes.")

    combined_df = dfs[base_alias]
    combined_aliases = {base_alias}

    # We'll attempt to iteratively apply joins where at least one side is already in combined_aliases
    remaining_joins = list(joins)

    while remaining_joins:
        progress = False
        next_joins: List[Dict[str, Any]] = []

        for j in remaining_joins:
            join_type = j.get("type", "inner").lower()
            left_ds = j["left_dataset"]
            right_ds = j["right_dataset"]
            on_spec = j.get("on") or []

            left_cols = [o["left_column"] for o in on_spec]
            right_cols = [o["right_column"] for o in on_spec]

            if left_ds in combined_aliases and right_ds in dfs:
                # combined_df (left) join new right_df
                right_df = dfs[right_ds]
                combined_df = combined_df.merge(
                    right_df,
                    left_on=left_cols,
                    right_on=right_cols,
                    how=join_type,
                )
                combined_aliases.add(right_ds)
                progress = True
            elif right_ds in combined_aliases and left_ds in dfs:
                # new left_df join combined_df (right)
                left_df = dfs[left_ds]
                combined_df = left_df.merge(
                    combined_df,
                    left_on=left_cols,
                    right_on=right_cols,
                    how=join_type,
                )
                combined_aliases.add(left_ds)
                progress = True
            else:
                # can't apply this join yet
                next_joins.append(j)

        if not progress:
            # We could not apply any remaining joins; likely the join graph is unsupported
            raise ValueError(
                "Could not resolve all joins with the current implementation. "
                "Check that joins form a connected graph starting from the first dataset."
            )

        remaining_joins = next_joins

    return combined_df


def execute_query_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a planner-generated query plan over local CSV files using pandas.

    Now supports:
      - One or more datasets loaded from local CSVs.
      - Joins between datasets (inner/left/right/outer) via 'joins' list.
      - Top-level filters (including on columns introduced by joins, e.g. 'region').
      - group_by, metrics, derived_columns, sort, limit.

    Expected plan keys (subset):
      - datasets: list of dataset dicts (name, alias, source, path)
      - joins: list of join specs (type, left_dataset, right_dataset, on)
      - filters: top-level filters (column -> {op: val})
      - group_by: list of columns
      - metrics: list of metric specs
      - derived_columns: list of {name, expression}
      - sort: list of {column, direction}
      - limit: optional int

    Returns:
      {
        "rows": [ {col: value, ...}, ... ],
        "meta": {
          "row_count": int,
          "group_by": [...],
          "metrics": [...],
        }
      }

    Raises ValueError for unsupported features or invalid plans.
    """
    datasets = plan.get("datasets") or []
    joins = plan.get("joins") or []
    filters = plan.get("filters") or {}
    group_by = plan.get("group_by") or []
    metrics = plan.get("metrics") or []
    derived_columns = plan.get("derived_columns") or []
    sort_spec = plan.get("sort") or []
    limit = plan.get("limit")

    # Load all datasets
    dfs = _load_datasets(datasets)

    # Apply joins (or return single dataset)
    df = _apply_joins(dfs, datasets, joins)

    # Apply top-level filters (e.g., year, agi_stub, age_class, region)
    df = _apply_filters(df, filters)

    if not group_by:
        raise ValueError("execute_query_plan currently requires a non-empty group_by.")

    # Compute metrics
    if metrics:
        result = _aggregate_metrics(df, group_by, metrics)
    else:
        # If no metrics, just return distinct group keys
        result = df[group_by].drop_duplicates().reset_index(drop=True)

    # Apply derived columns, using metric names as variables
    for d in derived_columns or []:
        name = d["name"]
        expr = d["expression"]
        # Use pandas.eval so expressions like "a - b" work
        result.eval(f"{name} = {expr}", inplace=True)

    # Apply sorting (your sample plan has sort: [], so this will often be skipped)
    if sort_spec:
        sort_cols: List[str] = []
        ascending: List[bool] = []
        for s in sort_spec:
            col = s["column"]
            direction = s.get("direction", "asc").lower()
            sort_cols.append(col)
            ascending.append(direction == "asc")
        result = result.sort_values(by=sort_cols, ascending=ascending)

    # Apply limit
    if limit is not None:
        try:
            n = int(limit)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid limit value: {limit!r}")
        result = result.head(n)

    rows = result.to_dict(orient="records")

    meta: Dict[str, Any] = {
        "row_count": int(len(rows)),
        "group_by": list(group_by),
        "metrics": [m["name"] for m in metrics],
    }

    return {
        "rows": rows,
        "meta": meta,
    }
