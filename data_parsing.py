import pandas as pd
import re
from pathlib import Path

# Directory where all your raw SOI CSVs are stored
DATA_DIR = Path("data/raw")

def extract_year_from_filename(fname):
    """
    Example: 1112inmigall.csv → second year = 12 → 2012
    """
    digits = re.findall(r"\d+", fname)[0]  # first numeric group, e.g. "1112"
    second_year = int(digits[2:4])
    return 2000 + second_year

def parse_raw_column(colname):
    """
    Parse column names like:
        total_n1_0
        outflow_y2_agi_5
        samest_y1_agi_6
    → (class, metric, age_class)
    """
    m = re.match(r"([^_]+)_(.+)_(\d+)$", colname)
    if not m:
        return None, None, None
    prefix = m.group(1)
    metric = m.group(2)     # n1, n2, y1_agi, y2_agi
    age_class = int(m.group(3))
    return prefix, metric, age_class

def parse_soi_file(path):
    """
    Parse a single SOI inmigall CSV into a tidy long format
    with metrics as separate columns.
    """
    df = pd.read_csv(path)
    year = extract_year_from_filename(path.name)

    id_cols = ["statefips", "state", "state_name", "agi_stub"]
    value_cols = [c for c in df.columns if c not in id_cols]

    # Melt to long form first
    long_df = df.melt(
        id_vars=id_cols,
        value_vars=value_cols,
        var_name="raw",
        value_name="value"
    )

    # Parse each column name
    long_df[["class", "metric", "age_class"]] = long_df["raw"].apply(
        lambda x: pd.Series(parse_raw_column(x))
    )

    # Now pivot so metric becomes wide: n1, n2, y1_agi, y2_agi
    wide_df = long_df.pivot_table(
        index=["statefips", "state", "state_name", "agi_stub", "class", "age_class"],
        columns="metric",
        values="value",
        aggfunc="sum"   # safe since there is no duplication
    ).reset_index()

    # Insert year column
    wide_df["year"] = year

    # Reorder columns
    metric_cols = ["n1", "n2", "y1_agi", "y2_agi"]
    final_cols = ["year", "statefips", "state", "state_name",
                  "agi_stub", "class", "age_class"] + metric_cols

    # Ensure missing metric columns are filled with NaN
    for m in metric_cols:
        if m not in wide_df:
            wide_df[m] = pd.NA

    wide_df = wide_df[final_cols]

    return wide_df

def soi_long_parse_all_years():
    all_files = sorted(DATA_DIR.glob("*inmigall*.csv"))
    frames = []
    for f in all_files:
        print(f"Parsing {f.name} ...")
        frames.append(parse_soi_file(f))
    return pd.concat(frames, ignore_index=True)

def parse_all_data():
    soi_long = soi_long_parse_all_years()
    soi_long.to_csv("data/processed/soi_migration_long.csv", index=False)
