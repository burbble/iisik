CREATE TABLE "USER" (
  user_id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  status VARCHAR(30) NOT NULL,
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE "ROLE" (
  role_id UUID PRIMARY KEY,
  name VARCHAR(80) UNIQUE NOT NULL,
  description VARCHAR(255)
);

CREATE TABLE "USER_ROLE" (
  user_id UUID NOT NULL,
  role_id UUID NOT NULL,
  assigned_at TIMESTAMP NOT NULL,
  PRIMARY KEY (user_id, role_id),
  FOREIGN KEY (user_id) REFERENCES "USER"(user_id),
  FOREIGN KEY (role_id) REFERENCES "ROLE"(role_id)
);
