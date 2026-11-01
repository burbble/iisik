CREATE TABLE "PROFITABILITY_READ_MODEL" (
  row_id UUID PRIMARY KEY,
  cost_version INTEGER NOT NULL,
  source_result_id UUID UNIQUE NOT NULL,
  product_id UUID NOT NULL,
  group_id UUID NOT NULL,
  period DATE NOT NULL,
  revenue DECIMAL(18,2) NOT NULL,
  total_cost DECIMAL(18,2) NOT NULL,
  profit DECIMAL(18,2) NOT NULL,
  margin_percent DECIMAL(7,2) NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE "SAVED_REPORT" (
  report_id UUID PRIMARY KEY,
  user_id UUID NOT NULL,
  name VARCHAR(200) NOT NULL,
  parameters JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE "REPORT_EXPORT" (
  export_id UUID PRIMARY KEY,
  report_id UUID NULL,
  requested_by UUID NOT NULL,
  format VARCHAR(20) NOT NULL,
  status VARCHAR(30) NOT NULL,
  file_ref VARCHAR(500) NULL,
  created_at TIMESTAMP NOT NULL,
  completed_at TIMESTAMP NULL,
  error_message TEXT NULL,
  FOREIGN KEY (report_id) REFERENCES "SAVED_REPORT"(report_id)
);
