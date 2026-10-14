from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("LAB7_DATA_DIR", os.getenv("LAB6_DATA_DIR", PROJECT_ROOT / ".data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)


def sqlite_url(filename: str) -> str:
    path = (DATA_DIR / filename).resolve().as_posix()
    return f"sqlite:///{path}"


def env(name: str, default: str) -> str:
    return os.getenv(name, default)


MASTER_DATA_GRPC_TARGET = env("MASTER_DATA_GRPC_TARGET", "127.0.0.1:50051")
PRODUCTION_GRPC_TARGET = env("PRODUCTION_GRPC_TARGET", "127.0.0.1:50052")
FINANCIAL_GRPC_TARGET = env("FINANCIAL_GRPC_TARGET", "127.0.0.1:50053")
COSTING_GRPC_TARGET = env("COSTING_GRPC_TARGET", "127.0.0.1:50054")
ANALYTICS_GRPC_TARGET = env("ANALYTICS_GRPC_TARGET", "127.0.0.1:50055")
REPORTING_GRPC_TARGET = env("REPORTING_GRPC_TARGET", "127.0.0.1:50056")

KAFKA_BOOTSTRAP_SERVERS = env("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
KAFKA_TOPIC = env("KAFKA_TOPIC", "profitability.events")
KAFKA_GROUP_PREFIX = env("KAFKA_GROUP_PREFIX", "profitability-lab7")
LAB7_EVENT_BACKEND = env("LAB7_EVENT_BACKEND", env("LAB6_EVENT_BACKEND", "kafka"))

REDIS_URL = env("REDIS_URL", "redis://127.0.0.1:6379/0")
LAB7_CACHE_BACKEND = env("LAB7_CACHE_BACKEND", "redis")
CACHE_KEY_PREFIX = env("CACHE_KEY_PREFIX", "lab7:cache")
COSTING_CONTEXT_CACHE_TTL_SECONDS = int(env("COSTING_CONTEXT_CACHE_TTL_SECONDS", "300"))

GRPC_TIMEOUT_SECONDS = float(env("GRPC_TIMEOUT_SECONDS", "2.0"))
GRPC_MAX_ATTEMPTS = int(env("GRPC_MAX_ATTEMPTS", "3"))
GRPC_RETRY_BACKOFF_SECONDS = float(env("GRPC_RETRY_BACKOFF_SECONDS", "0.05"))

KAFKA_MAX_ATTEMPTS = int(env("KAFKA_MAX_ATTEMPTS", "3"))
KAFKA_RETRY_BACKOFF_SECONDS = float(env("KAFKA_RETRY_BACKOFF_SECONDS", "0.10"))
KAFKA_DEAD_LETTER_TOPIC = env("KAFKA_DEAD_LETTER_TOPIC", f"{KAFKA_TOPIC}.dlq")

LOG_LEVEL = env("LOG_LEVEL", "INFO")
