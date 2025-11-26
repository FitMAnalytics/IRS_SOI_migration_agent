# CPI-U Reference and Deflators

## Overview

The **CPI-U reference table** provides annual Consumer Price Index values for All Urban Consumers (CPI-U). It is used to convert SOI migration income variables from **nominal dollars** to **constant (real) dollars**.

This is important when:
- comparing AGI across different years,
- analyzing migration-related income trends in real terms,
- aggregating or modeling long time series.

---

## File Location

- **Raw/reference CPI data**: `data/reference/CPI_U.csv`  


## Expected Columns in `CPI_U.csv`

### `year`
- **Type**: integer (YYYY)
- **Description**: Calendar year.

### `cpi_u`
- **Type**: numeric
- **Description**: Annual CPI-U index value for that year.

---

## Deflator Concept

To convert a nominal dollar value \( X_{y} \) in year `y` to **constant 2024 dollars**:

1. Compute a **deflator** for each year `y`:

   \[
   \text{deflator\_to\_2024}(y) = \frac{\text{CPI}_\text{2024}}{\text{CPI}_y}
   \]

2. Then define:

   \[
   X_{y}^{(2024)} = X_{y} \times \text{deflator\_to\_2024}(y)
   \]

Where:
- \( \text{CPI}_y \) is the CPI-U for year `y`,
- \( \text{CPI}_{2024} \) is the CPI-U for the base year.

---

## Example Usage in Python

```python
import pandas as pd

# Load CPI-U
cpi = pd.read_csv("data/reference/CPI_U.csv")

base_year = 2024
cpi_base = cpi.loc[cpi["year"] == base_year, "cpi_u"].iloc[0]

cpi["deflator_to_2024"] = cpi_base / cpi["cpi_u"]

- ** Note **
- All SOI monetary variables are nominal by default; using CPI-U deflators is recommended before cross-year comparisons.
- When changing base year, deflator needs to be recalculated.