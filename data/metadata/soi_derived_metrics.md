# SOI Migration Data – Derived Metrics and Default Definitions

This document defines common **derived metrics** used in analysis of IRS SOI migration data.

These definitions are **not raw columns** but formulas based on the cleaned dataset:

- `n1`, `n2`
- `y1_agi`, `y2_agi`
- `class` (inflow, outflow, total, nonmig, samest)
- `age_class`
- `agi_stub`

The agent should use these definitions unless the user explicitly instructs otherwise.

---

## 1. Default Basis for Rates and Percentages

Unless the user specifies a different basis, the agent should assume:

1. **Rates are based on `n1` (number of returns)**  
2. **Income flows use `y2_agi` (Year-2 AGI)**  
3. **Comparisons across years refer to Year-2 values**, matching the `year` variable in the processed dataset  
4. **Aggregates use `age_class = 0` and `agi_stub = 0`** unless stated  
5. **Net values = inflow − outflow**  
6. **Money values are nominal unless user requests CPI-U adjustment**

These defaults align with SOI methodology and typical usage in migration research.

---

## 2. Migration Rates (Standard Definitions)

### **Inflow Rate (default)**
\[
\text{inflow rate} = \frac{\text{inflow\_n1}}{\text{total\_n1}}
\]

### **Outflow Rate (default)**
\[
\text{outflow rate} = \frac{\text{outflow\_n1}}{\text{total\_n1}}
\]

### **Net Migration Rate (default)**
\[
\text{net migration rate} = \frac{\text{inflow\_n1} - \text{outflow\_n1}}{\text{total\_n1}}
\]

These are appropriate for most questions unless the user specifies “population-weighted”, “income-weighted”, etc.

---

## 3. Alternative Rate Bases (when explicitly specified)

### **Population-based (using `n2`)**

- **Inflow (population) rate**
  \[
  \frac{\text{inflow\_n2}}{\text{total\_n2}}
  \]

- **Outflow (population) rate**
  \[
  \frac{\text{outflow\_n2}}{\text{total\_n2}}
  \]

- **Net population migration**
  \[
  \text{inflow\_n2} - \text{outflow\_n2}
  \]

### **Income-based (using AGI)**  
Uses **Year-2 AGI (`y2_agi`)** unless otherwise stated.

- **Inflow AGI share**
  \[
  \frac{\text{inflow\_y2\_agi}}{\text{total\_y2\_agi}}
  \]

- **Outflow AGI share**
  \[
  \frac{\text{outflow\_y2\_agi}}{\text{total\_y2\_agi}}
  \]

- **Net FAGI**
  \[
  \text{net FAGI} = \text{inflow\_y2\_agi} - \text{outflow\_y2\_agi}
  \]

---

## 4. Absolute Migration Counts

### **Return counts**
- `inflow_n1` – number of tax returns moving into the state  
- `outflow_n1` – number of returns leaving the state  
- `samest_n1` – returns moving within the state  
- `nonmig_n1` – returns not changing address  

### **Population counts**
- `inflow_n2` – inflow of individuals (filers + dependents + joint filers)  
- `outflow_n2` – outflow of individuals  
- `samest_n2` – intrastate movers (population)  
- `nonmig_n2` – non-migrating individuals  

---

## 5. Income (FAGI) Flow Metrics

By default, use **Year-2 AGI** since it aligns with the `year` column:

- **Inflow FAGI**: `inflow_y2_agi`  
- **Outflow FAGI**: `outflow_y2_agi`  
- **Net FAGI**:
  \[
  \text{net FAGI} = \text{inflow\_y2\_agi} - \text{outflow\_y2\_agi}
  \]

Optional (if user requests):

- **Year-1 FAGI inflow/outflow**  
- Real (CPI-U adjusted) FAGI for constant-dollar analysis  

---

## 6. Conditioning on Income or Age

All metrics can be computed:

- for a single **age_class** (1–6),  
- for a single **AGI stub** (1–7),  
- or using aggregations:
  - `age_class = 0`: all ages  
  - `agi_stub = 0`: all AGI classes  

### Examples:
- “Migration rate of taxpayers aged 55–64” → `age_class = 5`
- “FAGI flows of millionaires” → `agi_stub = 7`

---

## 7. Combining Across Years

The `year` variable corresponds to the **second year** of the IRS two-year record.  
Thus:

- `y2_agi` matches `year`  
- `agi_stub` is classified by **Year-2 AGI**  
- Any cross-year analysis should treat values as belonging to the second year only

---

## 8. Adjusting for Inflation (CPI-U)

For real-dollar analysis:

\[
\text{AGI}^{(base)} = \text{AGI}^{(nominal)} \times \text{deflator}(year)
\]

Where deflators are defined in  
**`metadata/cpi_u_reference.md`**.

---

## 9. Guiding Principles for the Agent

When interpreting a user query:

1. If the user does **not** specify weighting → use `n1`.  
2. If the user asks about “people” or “population” → use `n2`.  
3. If the user asks about “income”, “FAGI”, “AGI”, or “money” → use `y2_agi`.  
4. If the user does not specify AGI or age group → use stub=0 and age_class=0.  
5. Net = inflow − outflow.  
6. Rates divide by `total_n1` by default.  
7. For real dollars, use CPI-U deflators only when explicitly requested.
8. If the user asks about the statistics of a region or a division, unless otherwise specified, treat that region/division as a whole.

This ensures consistent and predictable behavior across queries.
