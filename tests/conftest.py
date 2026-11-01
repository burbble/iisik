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
    for name in [
        "master_data",
        "production",
        "financial",
        "costing",
        "analytics",
        "reporting",
    ]:
        publisher = InMemoryEventPublisher()
        server, _ = build_server(name, publisher=publisher)
        server.start()
        servers.append(server)
        publishers[name] = publisher
    time.sleep(0.1)
    yield publishers
    for server in servers:
        server.stop(0)


@pytest.fixture(autouse=True)
def accounting_snapshots(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("IMPORT_DATA_DIR", str(tmp_path))
    production = [
        {
            "external_id": "TEST-ORDER",
            "product_code": "PD-1",
            "quantity": "10",
            "materials": [
                {"material_code": "PCB-01", "quantity": "10", "amount": "185"}
            ],
            "labor": [{"cost_center_code": "ASSEMBLY", "hours": "5", "amount": "150"}],
        }
    ]
    financial = [
        {
            "type": "OVERHEAD",
            "external_id": "TEST-OH",
            "cost_center_code": "ASSEMBLY",
            "amount": "20",
            "currency": "USD",
        },
        {
            "type": "SALE",
            "external_id": "TEST-SALE",
            "document_date": "2026-10-20",
            "currency": "USD",
            "items": [{"product_code": "PD-1", "quantity": "8", "revenue": "640"}],
        },
    ]
    for source, periods, records in [
        ("MES", ["2026-08-01", "2026-10-01"], production),
        ("FINANCE", ["2026-10-01"], financial),
    ]:
        folder = tmp_path / source
        folder.mkdir()
        for period in periods:
            (folder / f"{period}.json").write_text(json.dumps(records))
    return tmp_path
