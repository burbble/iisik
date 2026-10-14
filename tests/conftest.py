import os
import time
import pytest

os.environ.setdefault("LAB7_EVENT_BACKEND", "memory")
os.environ.setdefault("LAB7_SESSION_BACKEND", "memory")
os.environ.setdefault("LAB7_CACHE_BACKEND", "memory")


@pytest.fixture(scope="session", autouse=True)
def grpc_runtime():
    from app.transport.grpc.server import build_server
    from app.transport.kafka import InMemoryEventPublisher

    servers = []
    publishers = {}
    for name in ["master_data", "production", "financial", "costing", "analytics", "reporting"]:
        publisher = InMemoryEventPublisher()
        server, _ = build_server(name, publisher=publisher)
        server.start()
        servers.append(server)
        publishers[name] = publisher
    time.sleep(0.1)
    yield publishers
    for server in servers:
        server.stop(0)
