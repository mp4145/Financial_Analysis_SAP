"""
Finance Analytics MVP Data Generator
- Generates SAP-style finance data for Actuals vs Budget reporting
- Outputs CSVs
"""

from __future__ import annotations
import os
import sys
from dataclasses import dataclass
from datetime import date
import numpy as np
import pandas as pd


@dataclass
class Config:
    out_dir: str = "finance_mvp_data"
    seed: int = 42

    start_date: date = date(2024, 1, 1)
    end_date: date = date(2025, 12, 31)

    # Size knobs
    num_cost_centers: int = 12
    num_gl_accounts: int = 18

    # Posting behavior (actuals)
    avg_postings_opex_per_month: int = 4
    avg_postings_capex_per_month: int = 2
    max_postings_per_month: int = 14

    # Budget behavior
    base_opex: float = 3000.0
    base_capex: float = 8000.0

    # Realism knobs
    over_budget_cost_centers: int = 4
    under_budget_cost_centers: int = 3
    seasonal_q4_uplift: float = 0.15
    seasonal_summer_uplift: float = 0.05
    sparse_gl_probability: float = 0.35   # some GLs don't appear each month
    spike_probability: float = 0.03       # rare spikes
    spike_min: float = 0.25
    spike_max: float = 0.60


def make_dimensions(cfg: Config, rng: np.random.Generator):
    # Cost centers
    departments = [
        "FP&A", "Accounting", "Procurement", "Treasury", "Operations", "Sales Ops",
        "IT Finance", "Corporate", "R&D", "Manufacturing", "Logistics", "Facilities"
    ]
    departments = departments[: cfg.num_cost_centers]

    cc_ids = [f"CC{str(i).zfill(4)}" for i in range(1, cfg.num_cost_centers + 1)]
    managers = [
        "A. Patel", "J. Kim", "M. Chen", "S. Rivera", "D. Johnson", "L. Singh",
        "N. Garcia", "K. Brown", "R. Ahmed", "T. Nguyen", "P. Wilson", "E. Martinez"
    ][: cfg.num_cost_centers]

    cost_centers = pd.DataFrame({
        "cost_center_id": cc_ids,
        "cost_center_name": [f"{d} Cost Center" for d in departments],
        "department": departments,
        "manager": managers,
        "parent_cost_center_id": [None] * cfg.num_cost_centers
    })

    # GL accounts (SAP-like)
    gl_defs = [
        ("600000","Salaries & Wages","OPEX","Payroll"),
        ("601000","Benefits","OPEX","Payroll"),
        ("602000","Contractors","OPEX","Payroll"),
        ("610000","Software & Subscriptions","OPEX","IT"),
        ("611000","Cloud Infrastructure","OPEX","IT"),
        ("620000","Travel & Entertainment","OPEX","G&A"),
        ("630000","Marketing Spend","OPEX","Sales"),
        ("640000","Office Supplies","OPEX","G&A"),
        ("650000","Rent & Utilities","OPEX","Facilities"),
        ("660000","Professional Services","OPEX","G&A"),
        ("670000","Training & Education","OPEX","G&A"),
        ("680000","Insurance","OPEX","G&A"),
        ("700000","Capital Equipment","CAPEX","Capex"),
        ("701000","IT Hardware","CAPEX","Capex"),
        ("702000","Facility Improvements","CAPEX","Capex"),
        ("710000","Depreciation","OPEX","G&A"),
        ("720000","Freight & Shipping","OPEX","Ops"),
        ("730000","Maintenance","OPEX","Facilities"),
    ]
    gl_defs = gl_defs[: cfg.num_gl_accounts]

    gl_accounts = pd.DataFrame(gl_defs, columns=["gl_account","gl_name","account_type","gl_group"])

    # Fiscal calendar (calendar fiscal year for MVP; you can adjust to a 4-4-5 later)
    dates = pd.date_range(cfg.start_date, cfg.end_date, freq="D")
    fiscal_calendar = pd.DataFrame({
        "calendar_date": dates,
        "fiscal_year": dates.year.astype(int),
        "fiscal_period": dates.month.astype(int),
        "is_month_end": dates.is_month_end
    })

    return cost_centers, gl_accounts, fiscal_calendar


def generate_budget(cfg: Config, rng: np.random.Generator, cost_centers: pd.DataFrame, gl_accounts: pd.DataFrame):
    months = pd.period_range(cfg.start_date, cfg.end_date, freq="M")

    # Some GLs are sparse (appear in fewer months) to mimic reality
    sparse_gls = set(["620000", "640000", "670000", "700000", "701000", "702000"]) & set(gl_accounts["gl_account"].tolist())

    cc_ids = cost_centers["cost_center_id"].tolist()
    gl_rows = gl_accounts.to_dict(orient="records")

    budget_rows = []
    for p in months:
        fy, fp = int(p.year), int(p.month)

        for cc_i, cc in enumerate(cc_ids):
            # cost center scale (some CCs are bigger)
            cc_scale = 0.8 + (cc_i / max(1, len(cc_ids)-1)) * 0.8  # 0.8..1.6

            for gl_i, gl in enumerate(gl_rows):
                gl_code = gl["gl_account"]
                acct_type = gl["account_type"]

                # skip sparse GLs sometimes
                if gl_code in sparse_gls and rng.random() < cfg.sparse_gl_probability:
                    continue

                base = cfg.base_opex if acct_type == "OPEX" else cfg.base_capex

                # GL scale (some accounts are naturally larger)
                gl_scale = 0.6 + (gl_i / max(1, len(gl_rows)-1)) * 1.2  # 0.6..1.8

                # seasonality: Q4 uplift; summer slight uplift
                seasonal = 1.0
                if fp in [10, 11, 12]:
                    seasonal += cfg.seasonal_q4_uplift
                elif fp in [6, 7, 8]:
                    seasonal += cfg.seasonal_summer_uplift

                noise = rng.normal(1.0, 0.08)
                amt = max(0.0, base * cc_scale * gl_scale * seasonal * noise)

                budget_rows.append((fy, fp, gl_code, cc, round(float(amt), 2)))

    budget = pd.DataFrame(
        budget_rows,
        columns=["fiscal_year","fiscal_period","gl_account","cost_center_id","budget_amount"]
    )

    # Ensure uniqueness at grain (FY, period, CC, GL)
    dupes = budget.duplicated(subset=["fiscal_year","fiscal_period","gl_account","cost_center_id"]).sum()
    if dupes:
        raise ValueError(f"Budget grain not unique; duplicates found: {dupes}")

    return budget


def generate_actuals(cfg: Config, rng: np.random.Generator, budget: pd.DataFrame, gl_accounts: pd.DataFrame):
    months = pd.period_range(cfg.start_date, cfg.end_date, freq="M")

    # Pick some CCs to trend over/under budget
    cc_ids = sorted(budget["cost_center_id"].unique().tolist())
    over_budget_cc = set(rng.choice(cc_ids, size=min(cfg.over_budget_cost_centers, len(cc_ids)), replace=False))
    remaining = [c for c in cc_ids if c not in over_budget_cc]
    under_budget_cc = set(rng.choice(remaining, size=min(cfg.under_budget_cost_centers, len(remaining)), replace=False))

    gl_type = dict(zip(gl_accounts["gl_account"], gl_accounts["account_type"]))
    doc_types = ["SA", "KR", "RE", "AB", "KA"]

    # Precompute daily date arrays for each (fy, fp)
    dates_by_period = {}
    for p in months:
        start = p.to_timestamp()
        end = (p + 1).to_timestamp() - pd.Timedelta(days=1)
        dates_by_period[(int(p.year), int(p.month))] = pd.date_range(start, end, freq="D")

    actual_rows = []
    # Group budget at target grain (it already is, but keep it robust)
    budget_g = budget.groupby(["fiscal_year","fiscal_period","gl_account","cost_center_id"], as_index=False)["budget_amount"].sum()

    for _, row in budget_g.iterrows():
        fy = int(row.fiscal_year)
        fp = int(row.fiscal_period)
        gl = row.gl_account
        cc = row.cost_center_id
        bud = float(row.budget_amount)

        # multiplier around 1.0 to create realistic variance
        mult = rng.normal(1.0, 0.12)
        if cc in over_budget_cc:
            mult += 0.08
        if cc in under_budget_cc:
            mult -= 0.07
        if rng.random() < cfg.spike_probability:
            mult += float(rng.uniform(cfg.spike_min, cfg.spike_max))

        target_actual = max(0.0, bud * mult)

        # number of postings
        lam = cfg.avg_postings_opex_per_month if gl_type.get(gl) == "OPEX" else cfg.avg_postings_capex_per_month
        n = int(np.clip(rng.poisson(lam), 1, cfg.max_postings_per_month))

        dates_in_month = dates_by_period[(fy, fp)]
        post_dates = rng.choice(dates_in_month, size=n, replace=True)

        # split into n transactions
        weights = rng.dirichlet(np.ones(n))
        amounts = target_actual * weights

        for d, amt in zip(post_dates, amounts):
            actual_rows.append((
                pd.Timestamp(d).date(),
                fy,
                fp,
                gl,
                cc,
                round(float(amt), 2),
                str(rng.choice(doc_types))
            ))

    actuals = pd.DataFrame(
        actual_rows,
        columns=["posting_date","fiscal_year","fiscal_period","gl_account","cost_center_id","actual_amount","document_type"]
    )

    return actuals


def validate(cost_centers, gl_accounts, fiscal_calendar, budget, actuals):
    # Referential integrity checks
    assert set(budget["cost_center_id"]).issubset(set(cost_centers["cost_center_id"]))
    assert set(actuals["cost_center_id"]).issubset(set(cost_centers["cost_center_id"]))
    assert set(budget["gl_account"]).issubset(set(gl_accounts["gl_account"]))
    assert set(actuals["gl_account"]).issubset(set(gl_accounts["gl_account"]))

    # Date range checks
    assert actuals["posting_date"].min() >= fiscal_calendar["calendar_date"].min().date()
    assert actuals["posting_date"].max() <= fiscal_calendar["calendar_date"].max().date()

    # Budget grain uniqueness
    assert not budget.duplicated(["fiscal_year","fiscal_period","gl_account","cost_center_id"]).any()

    # Basic sanity: non-negative budget; actuals can be positive (you can add reversals later)
    assert (budget["budget_amount"] >= 0).all()


def main():
    cfg = Config()
    os.makedirs(cfg.out_dir, exist_ok=True)

    rng = np.random.default_rng(cfg.seed)

    cost_centers, gl_accounts, fiscal_calendar = make_dimensions(cfg, rng)
    budget = generate_budget(cfg, rng, cost_centers, gl_accounts)
    actuals = generate_actuals(cfg, rng, budget, gl_accounts)

    validate(cost_centers, gl_accounts, fiscal_calendar, budget, actuals)

    # Write CSVs
    cost_centers.to_csv(os.path.join(cfg.out_dir, "cost_centers.csv"), index=False)
    gl_accounts.to_csv(os.path.join(cfg.out_dir, "gl_accounts.csv"), index=False)
    fiscal_calendar.to_csv(os.path.join(cfg.out_dir, "fiscal_calendar.csv"), index=False)
    budget.to_csv(os.path.join(cfg.out_dir, "finance_budget.csv"), index=False)
    actuals.to_csv(os.path.join(cfg.out_dir, "finance_actuals.csv"), index=False)

    print("Generated datasets:")
    print(f"- {cfg.out_dir}/cost_centers.csv ({len(cost_centers):,} rows)")
    print(f"- {cfg.out_dir}/gl_accounts.csv ({len(gl_accounts):,} rows)")
    print(f"- {cfg.out_dir}/fiscal_calendar.csv ({len(fiscal_calendar):,} rows)")
    print(f"- {cfg.out_dir}/finance_budget.csv ({len(budget):,} rows)")
    print(f"- {cfg.out_dir}/finance_actuals.csv ({len(actuals):,} rows)")
    print(f"Date range: {actuals['posting_date'].min()} → {actuals['posting_date'].max()}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
