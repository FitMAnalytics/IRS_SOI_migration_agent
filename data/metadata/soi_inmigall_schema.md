# SOI State-level Migration Data: `inmigall` (Processed Schema)

## Overview

This dataset contains **state-level migration statistics** derived from IRS SOI "individual income tax returns with migration data" (`inmigall`) files.

The IRS defines a "migrant" as a tax unit that:
- Filed returns in **two consecutive tax years**, and  
- Had a **change in mailing address** between those two years.

Each record in the processed table corresponds to:
- a **state**  
- an **AGI income class (`agi_stub`)**  
- an **age class**  
- a **movement class** (inflow, outflow, etc.)  
- a single **calendar year** (the second year in the IRS 2-year comparison)

All monetary values are currently in **nominal dollars** for that calendar year.

---

## File Location

- **Processed data**: `data/processed/soi_migration_long.csv`

This file is created by the SOI parsing script that:
- reads all `*inmigall*.csv` files from `data/raw/`
- extracts the second year from the filename
- reshapes the wide SOI layout into a tidy panel

---

## Column Dictionary

### `year`
- **Type**: integer (YYYY)
- **Description**: Calendar year corresponding to the **second year** in the SOI file name. This should be interpreted as the year of migration.
  - Example: file `1112inmigall.csv` → `year = 2012`.

---

### `statefips`
- **Type**: integer
- **Description**: 2-digit FIPS code for the state.
- **Reference**: see `data/reference/statefips_dict.csv` and `metadata/state_fips_reference.md`.

---

### `state`
- **Type**: string
- **Description**: 2-letter state abbreviation (e.g., `MN`).

---

### `state_name`
- **Type**: string
- **Description**: Full state name (e.g., `Minnesota`).

---

### `agi_stub`
- **Type**: integer
- **Description**: IRS SOI “Adjusted Gross Income (AGI) class” indicator.  
  Each stub corresponds to an IRS-defined AGI bracket, used consistently across all SOI migration datasets.

- **Values (official thresholds)**:
  - `0` — All AGI classes combined  
  - `1` — $1 to under $10,000  
  - `2` — $10,000 to under $25,000  
  - `3` — $25,000 to under $50,000  
  - `4` — $50,000 to under $75,000  
  - `5` — $75,000 to under $100,000  
  - `6` — $100,000 to under $200,000  
  - `7` — $200,000 or more  

- **Note**:
    These stubs partition the filing population into mutually exclusive income bins.  
    Stub `0` is not an income bin; it is the **aggregate of all AGI classes**.
    Because the stub is based on **Year-2 AGI**, it matches the destination-year income (`y2_agi`) and the `year` variable in the processed dataset.

---

### `class`
- **Type**: string
- **Description**: Migration/movement class for filers in this state, AGI stub, and age class.
- **Allowed values**:
  - `total` – All filers whose prior-year address was in this state  
  - `nonmig` – Filers whose mailing address did **not** change between the two years  
  - `outflow` – Filers who **moved out** of this state to another state  
  - `inflow` – Filers who **moved into** this state from another state  
  - `samest` – Filers who moved **within the same state** (changed address but did not cross state lines)

Note: For a given state/agi_stub/age_class, we expect approximately:
`total ≈ nonmig + outflow + samest`.
Both `inflow` and `outflow` only consider interstate migration; `samest` consider migration within the state (for example, someone moves from Minneapolis, MN to St Paul, MN).

---

### `age_class`
- **Type**: integer
- **Description**: Age category of the primary taxpayer.
- **Values**:
  - `0`: All ages combined  
  - `1`: 0-25  
  - `2`: 26–34  
  - `3`: 35–44  
  - `4`: 45–54  
  - `5`: 55–64  
  - `6`: 65 and over  

---

### `n1`
- **Type**: integer
- **Description**: Number of **tax returns** in this state / AGI stub / movement class / age class.
- **Year reference**: Based on SOI definition for the two-year comparison; typically associated with the second-year filing universe.

---

### `n2`
- **Type**: integer
- **Description**: Number of **individuals** in this group (filers + dependents + joint filers) in this state / AGI stub / movement class / age class.

---

### `y1_agi`
- **Type**: numeric
- **Units**: nominal dollars (year-specific), in thousand.
- **Description**: Sum of **adjusted gross income in the first year (first year = `year` - 1)** of the two-year pair, for this state / AGI stub / movement class / age class.

---

### `y2_agi`
- **Type**: numeric
- **Units**: nominal dollars (year-specific), in thousand.
- **Description**: Sum of **adjusted gross income in the second year (this is consistent with the value of `year` column)** of the two-year pair, for this state / AGI stub / movement class / age class.
- **Note**: This is often the main measure used when focusing on income in the destination year (i.e., the `year` column).

---

## Notes and Caveats

- All monetary variables (`y1_agi`, `y2_agi`) are **nominal**, not deflated. To convert to a constant base year (e.g., 2025 dollars), join with CPI-U deflators described in `metadata/cpi_u_reference.md`.
- All monetary values are in thousand.
- State identifiers can be enriched using the FIPS reference table in `data/reference/statefips_dict.csv`.
