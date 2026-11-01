CREATE TABLE "COST_CALCULATION" (
  calculation_id UUID PRIMARY KEY,
  product_id UUID NOT NULL,
  period DATE NOT NULL,
  version INTEGER NOT NULL,
  status VARCHAR(30) NOT NULL,
  material_cost DECIMAL(18,2) NOT NULL,
  labor_cost DECIMAL(18,2) NOT NULL,
  overhead_cost DECIMAL(18,2) NOT NULL,
  total_cost DECIMAL(18,2) NOT NULL,
  produced_qty DECIMAL(18,4) NOT NULL,
  unit_cost DECIMAL(18,4) NOT NULL,
  source_versions JSON NOT NULL,
  planned_unit_cost DECIMAL(18,4),
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE "OVERHEAD_ALLOCATION" (
  allocation_id UUID PRIMARY KEY,
  calculation_id UUID NOT NULL,
  production_order_id UUID NOT NULL,
  cost_center_id UUID NOT NULL,
  basis_type VARCHAR(40) NOT NULL,
  basis_value DECIMAL(18,4) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  FOREIGN KEY (calculation_id) REFERENCES "COST_CALCULATION"(calculation_id)
);

CREATE TABLE "OUTBOX_EVENT" (
  event_id UUID PRIMARY KEY,
  envelope JSON NOT NULL,
  published_at TIMESTAMP NULL,
  last_error TEXT NULL
);
