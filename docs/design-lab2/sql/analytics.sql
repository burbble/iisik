CREATE TABLE "PROFITABILITY_RESULT" (
  result_id UUID PRIMARY KEY,
  calculation_id UUID UNIQUE NOT NULL,
  product_id UUID NOT NULL,
  period DATE NOT NULL,
  revenue DECIMAL(18,2) NOT NULL,
  cost_of_sales DECIMAL(18,2) NOT NULL,
  profit DECIMAL(18,2) NOT NULL,
  margin_percent DECIMAL(7,2) NOT NULL,
  cost_version INTEGER NOT NULL,
  status VARCHAR(30) NOT NULL,
  calculated_at TIMESTAMP NOT NULL
);

CREATE TABLE "PROFITABILITY_AGGREGATE" (
  aggregate_id UUID PRIMARY KEY,
  dimension_type VARCHAR(30) NOT NULL,
  dimension_id UUID NOT NULL,
  period DATE NOT NULL,
  revenue DECIMAL(18,2) NOT NULL,
  total_cost DECIMAL(18,2) NOT NULL,
  profit DECIMAL(18,2) NOT NULL,
  margin_percent DECIMAL(7,2) NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE "CALCULATION_JOB" (
  job_id UUID PRIMARY KEY,
  status VARCHAR(30) NOT NULL CHECK (status IN ('COMPLETED', 'INVALIDATED')),
  period DATE NOT NULL,
  product_ids JSON NOT NULL
);
