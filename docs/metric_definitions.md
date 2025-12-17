# Metric Definitions

This document defines the key financial metrics used across all dashboards to ensure consistency, transparency, and trust.

---

## Actual Spend
**Definition:**  
Total posted financial spend for a given fiscal period.

**Calculation:**  
`SUM(Actual)`


**Notes:**  
- Represents realized costs
- Assumed to be sourced from finalized financial postings

---

## Budget
**Definition:**  
Approved budget amount for the same fiscal period.

**Calculation:**  
`SUM(Budget)`


**Notes:**  
- Serves as the baseline for variance analysis
- Assumed to be static within a fiscal year

---

## Variance ($)
**Definition:**  
Difference between actual spend and budget.

**Calculation:**  
`Variance $ = SUM(Actual) - SUM(Budget)`


**Interpretation:**  
- Positive value → Over budget
- Negative value → Under budget

---

## Variance (%)
**Definition:**  
Percentage difference between actual spend and budget.

**Calculation:**  
`Variance % = (SUM(Actual) - SUM(Budget)) / SUM(Budget)`


**Interpretation:**  
- Indicates relative severity of variance
- Used for executive-level performance assessment

---

## YTD Actual
**Definition:**  
Cumulative actual spend from the start of the fiscal year through the selected fiscal period.

**Calculation:**  
`RUNNING_SUM(SUM(Actual))`


---

## YTD Budget
**Definition:**  
Cumulative budget from the start of the fiscal year through the selected fiscal period.

**Calculation:**  
`RUNNING_SUM(SUM(Budget))`


---

## Budget Utilization (%)
**Definition:**  
Percentage of the annual budget consumed year-to-date.

**Calculation:**  
`Budget Utilization % = SUM(Actual) / SUM(Budget)`


**Interpretation:**  
- >100% indicates overspend
- <100% indicates remaining budget capacity

---

## Absolute Variance
**Definition:**  
Magnitude of variance regardless of direction, used for ranking material drivers.

**Calculation:**  
`ABS(Variance $)`


---

## Dimensional Definitions
- **Cost Center:** Organizational unit responsible for spend
- **GL Account:** Account classification identifying the nature of spend
- **Account Type:** High-level classification (e.g., OPEX, CAPEX)
- **Department:** Functional grouping within the organization
