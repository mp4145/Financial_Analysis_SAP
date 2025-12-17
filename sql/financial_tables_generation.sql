-- Create tables 
-- DIMENSIONS
CREATE TABLE cost_centers (
  cost_center_id   VARCHAR(16) PRIMARY KEY,
  cost_center_name TEXT NOT NULL,
  department       TEXT NOT NULL,
  manager          TEXT NOT NULL,
  parent_cost_center_id VARCHAR(16)
);

CREATE TABLE gl_accounts (
  gl_account   VARCHAR(16) PRIMARY KEY,
  gl_name      TEXT NOT NULL,
  account_type VARCHAR(8) NOT NULL,
  gl_group     TEXT NOT NULL
);

CREATE TABLE fiscal_calendar (
  calendar_date DATE PRIMARY KEY,
  fiscal_year   INT NOT NULL,
  fiscal_period INT NOT NULL,
  is_month_end  BOOLEAN NOT NULL
);

-- FACTS
CREATE TABLE finance_budget (
  fiscal_year    INT NOT NULL,
  fiscal_period  INT NOT NULL,
  gl_account     VARCHAR(16) NOT NULL,
  cost_center_id VARCHAR(16) NOT NULL,
  budget_amount  NUMERIC(18,2) NOT NULL,
  PRIMARY KEY (fiscal_year, fiscal_period, gl_account, cost_center_id)
);

CREATE TABLE finance_actuals (
  posting_date   DATE NOT NULL,
  fiscal_year    INT NOT NULL,
  fiscal_period  INT NOT NULL,
  gl_account     VARCHAR(16) NOT NULL,
  cost_center_id VARCHAR(16) NOT NULL,
  actual_amount  NUMERIC(18,2) NOT NULL,
  document_type  VARCHAR(4) NOT NULL
);

-- Import csvs to these tables 

-- Sanity Checks
select COUNT(*) from cost_centers;
select COUNT(*) from finance_actuals;
select COUNT(*) from finance_budget;
select COUNT(*) from fiscal_calendar;
select COUNT(*) from gl_accounts;

-- Curated View
CREATE OR REPLACE VIEW finance_mart_monthly AS
WITH actuals_monthly AS (
    SELECT
        fiscal_year,
        fiscal_period,
        cost_center_id,
        gl_account,
        SUM(actual_amount)::numeric(18,2) AS actual_amount
    FROM finance_actuals
    GROUP BY 1,2,3,4
),
budget_monthly AS (
    SELECT
        fiscal_year,
        fiscal_period,
        cost_center_id,
        gl_account,
        SUM(budget_amount)::numeric(18,2) AS budget_amount
    FROM finance_budget
    GROUP BY 1,2,3,4
)
SELECT
    COALESCE(a.fiscal_year, b.fiscal_year)      AS fiscal_year,
    COALESCE(a.fiscal_period, b.fiscal_period)  AS fiscal_period,
    COALESCE(a.cost_center_id, b.cost_center_id) AS cost_center_id,
    COALESCE(a.gl_account, b.gl_account)        AS gl_account,

    COALESCE(a.actual_amount, 0) AS actual_amount,
    COALESCE(b.budget_amount, 0) AS budget_amount,

    (COALESCE(a.actual_amount, 0) - COALESCE(b.budget_amount, 0)) 
        AS variance_amount,

    CASE 
        WHEN COALESCE(b.budget_amount, 0) = 0 THEN NULL
        ELSE (COALESCE(a.actual_amount, 0) - COALESCE(b.budget_amount, 0)) 
             / b.budget_amount
    END AS variance_pct
FROM actuals_monthly a
FULL OUTER JOIN budget_monthly b
  ON a.fiscal_year = b.fiscal_year
 AND a.fiscal_period = b.fiscal_period
 AND a.cost_center_id = b.cost_center_id
 AND a.gl_account = b.gl_account;

select * from finance_mart_monthly; 

-- Actuals Reconciliation (Must match)
SELECT
  (SELECT SUM(actual_amount) FROM finance_actuals) AS raw_actuals,
  (SELECT SUM(actual_amount) FROM finance_mart_monthly) AS mart_actuals;

-- Budget Reconciliation (Must match)
SELECT
  (SELECT SUM(budget_amount) FROM finance_budget) AS raw_budget,
  (SELECT SUM(budget_amount) FROM finance_mart_monthly) AS mart_budget;

-- Grain Check (should return 0 rows)
SELECT fiscal_year, fiscal_period, cost_center_id, gl_account, COUNT(*) AS cnt
FROM finance_mart_monthly
GROUP BY 1,2,3,4
HAVING COUNT(*) > 1;

-- Usability Test
SELECT
  f.fiscal_year,
  f.fiscal_period,
  c.department,
  g.gl_group,
  SUM(f.actual_amount) AS actual,
  SUM(f.budget_amount) AS budget
FROM finance_mart_monthly f
JOIN cost_centers c ON f.cost_center_id = c.cost_center_id
JOIN gl_accounts g ON f.gl_account = g.gl_account
GROUP BY 1,2,3,4
ORDER BY 1,2;

-- Download the mart view to upload to Tableau public
SELECT *
FROM finance_mart_monthly
ORDER BY fiscal_year, fiscal_period, cost_center_id, gl_account;