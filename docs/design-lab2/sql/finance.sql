CREATE TABLE "SALES_DOCUMENT" (
  sales_document_id UUID PRIMARY KEY,
  external_id VARCHAR(80) UNIQUE NOT NULL,
  document_date DATE NOT NULL,
  customer_ref VARCHAR(80),
  currency CHAR(3) NOT NULL
);

CREATE TABLE "SALES_ITEM" (
  sales_item_id UUID PRIMARY KEY,
  sales_document_id UUID NOT NULL,
  product_id UUID NOT NULL,
  quantity DECIMAL(18,4) NOT NULL,
  revenue DECIMAL(18,2) NOT NULL,
  discount DECIMAL(18,2) NOT NULL,
  FOREIGN KEY (sales_document_id) REFERENCES "SALES_DOCUMENT"(sales_document_id)
);

CREATE TABLE "FINANCIAL_ENTRY" (
  entry_id UUID PRIMARY KEY,
  external_id VARCHAR(80) UNIQUE NOT NULL,
  period DATE NOT NULL,
  cost_center_id UUID NOT NULL,
  entry_type VARCHAR(30) NOT NULL,
  amount DECIMAL(18,2) NOT NULL,
  currency CHAR(3) NOT NULL,
  posted_at TIMESTAMP NOT NULL
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
