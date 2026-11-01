CREATE TABLE "PRODUCT_GROUP" (
  group_id UUID PRIMARY KEY,
  parent_id UUID NULL,
  code VARCHAR(40) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  FOREIGN KEY (parent_id) REFERENCES "PRODUCT_GROUP"(group_id)
);

CREATE TABLE "PRODUCT" (
  product_id UUID PRIMARY KEY,
  group_id UUID NOT NULL,
  code VARCHAR(40) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  unit VARCHAR(20) NOT NULL,
  active BOOLEAN NOT NULL,
  FOREIGN KEY (group_id) REFERENCES "PRODUCT_GROUP"(group_id)
);

CREATE TABLE "MATERIAL" (
  material_id UUID PRIMARY KEY,
  code VARCHAR(40) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  unit VARCHAR(20) NOT NULL,
  standard_price DECIMAL(18,2)
);

CREATE TABLE "PRODUCT_MATERIAL" (
  product_id UUID NOT NULL,
  material_id UUID NOT NULL,
  valid_from DATE NOT NULL,
  standard_qty DECIMAL(18,4) NOT NULL,
  valid_to DATE NULL,
  PRIMARY KEY (product_id, material_id, valid_from),
  FOREIGN KEY (product_id) REFERENCES "PRODUCT"(product_id),
  FOREIGN KEY (material_id) REFERENCES "MATERIAL"(material_id)
);

CREATE TABLE "COST_CENTER" (
  cost_center_id UUID PRIMARY KEY,
  code VARCHAR(40) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  allocation_base VARCHAR(40) NOT NULL
);

CREATE TABLE "EXTERNAL_MAPPING" (
  mapping_id UUID PRIMARY KEY,
  source_system VARCHAR(80) NOT NULL,
  entity_type VARCHAR(40) NOT NULL,
  external_code VARCHAR(80) NOT NULL,
  internal_id UUID NOT NULL,
  status VARCHAR(30) NOT NULL,
  updated_at TIMESTAMP NOT NULL
);

CREATE TABLE "PLANNED_COST" (
  plan_id UUID PRIMARY KEY,
  product_id UUID NOT NULL REFERENCES "PRODUCT"(product_id),
  period DATE NOT NULL,
  version INTEGER NOT NULL,
  unit_cost DECIMAL(18,4) NOT NULL,
  status VARCHAR(30) NOT NULL,
  UNIQUE(product_id, period, version)
);
