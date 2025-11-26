# State FIPS Reference Table

## Overview

The **state FIPS reference table** provides a standardized mapping between:
- numeric state FIPS codes,
- 2-letter postal state abbreviations,
- full state names,
- Census **four-region** classification, and
- Census **nine-division** classification.

These geographic attributes follow the official U.S. Census Bureau definitions.

This table is used to:
- interpret the `statefips` and `state` columns in SOI migration data,
- group or filter migration flows by Census region or Census division,
- support user queries such as “Midwest”, “Pacific division”, “South Atlantic”, etc.,
- ensure consistent geographic aggregation throughout the analysis pipeline.

---

## File Location

- **Reference data**: `data/reference/statefips_dict.csv`

---

## Expected Columns

### `statefips`
- **Type**: integer  
- **Description**: 2-digit FIPS code for the state (e.g., `27` for Minnesota).  

---

### `state`
- **Type**: string  
- **Description**: 2-letter state abbreviation (e.g., `MN`).  
- **Notes**: Used as the primary join key in most SOI datasets.

---

### `state_name`
- **Type**: string  
- **Description**: Full state name in uppercase (e.g., `MINNESOTA`).  

---

### `region`
- **Type**: string  
- **Description**: U.S. Census **four-region** grouping.  
- **Allowed values**:
  - `Northeast`
  - `Midwest`
  - `South`
  - `West`

- **Purpose**:
  - Allows users to request aggregated results such as:
    - “Northeast net migration”
    - “South vs West inflow comparison”
  - Enables the Query Planner to automatically expand region terms into state lists.

---

### `division`
- **Type**: string  
- **Description**: U.S. Census **nine-division** classification, nested within regions.  
- **Allowed values**:
  - `New England`
  - `Middle Atlantic`
  - `East North Central`
  - `West North Central`
  - `South Atlantic`
  - `East South Central`
  - `West South Central`
  - `Mountain`
  - `Pacific`

- **Purpose**:
  - Supports finer geographic selections such as:
    - “Mountain division migration”
    - “New England outflows since 2010”
  - Critical for expanding user queries referring to Census divisions.

---

## Notes and Usage

- LLM agents receive this table as part of its metadata.  
  One should **never guess** the states within a region or division; it must use the mappings in this reference file.

- Analysts can join this table onto:
  - SOI migration data (`soi_migration_long`)
  - state-level demographic data
  - population or economic indicators  
  to enable geographic aggregation.

- Region and division definitions are fixed and correspond to Census Bureau standards.  
  If these mappings ever change, update **only** this file—no prompt changes required.
