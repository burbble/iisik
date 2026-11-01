CREATE TABLE "PRODUCTION_ORDER" (
  order_id UUID PRIMARY KEY,
  external_id VARCHAR(80) UNIQUE NOT NULL,
  product_id UUID NOT NULL,
  period DATE NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  status VARCHAR(30) NOT NULL
);

CREATE TABLE "MATERIAL_CONSUMPTION" (
  consumption_id UUID PRIMARY KEY,
  order_id UUID NOT NULL,
  material_id UUID NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  posted_at TIMESTAMP NOT NULL,
  FOREIGN KEY (order_id) REFERENCES "PRODUCTION_ORDER"(order_id)
);

CREATE TABLE "LABOR_ENTRY" (
  labor_entry_id UUID PRIMARY KEY,
  order_id UUID NOT NULL,
  cost_center_id UUID NOT NULL,
  hours DECIMAL(12,2) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  FOREIGN KEY (order_id) REFERENCES "PRODUCTION_ORDER"(order_id)
);

CREATE TABLE "IMPORT_RUN" (
  import_run_id UUID PRIMARY KEY,
  source_system VARCHAR(80) NOT NULL,
  period DATE NOT NULL,
  status VARCHAR(30) NOT NULL,
  records_loaded INTEGER NOT NULL,
  records_failed INTEGER NOT NULL,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP NULL
);

CREATE TABLE "IMPORT_ERROR" (
  error_id UUID PRIMARY KEY,
  import_run_id UUID NOT NULL,
  record_key VARCHAR(120),
  error_code VARCHAR(50) NOT NULL,
  message TEXT NOT NULL,
  raw_payload JSONB NULL,
  FOREIGN KEY (import_run_id) REFERENCES "IMPORT_RUN"(import_run_id)
);

CREATE TABLE "OUTBOX_EVENT" (
  event_id UUID PRIMARY KEY,
  envelope JSON NOT NULL,
  published_at TIMESTAMP NULL,
  last_error TEXT NULL
);
