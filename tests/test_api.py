# tests/test_api.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Campaign, Recipient

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def setup_function():
    Base.metadata.create_all(test_engine)


def teardown_function():
    Base.metadata.drop_all(test_engine)


client = TestClient(app)


def _seed_campaign() -> int:
    db = TestSession()
    c = Campaign(name="Test Campaign", subject="Hi", body="Hello there")
    db.add(c)
    db.commit()
    db.refresh(c)
    campaign_id = c.id
    for i in range(5):
        db.add(Recipient(campaign_id=campaign_id, email=f"user{i}@example.com"))
    db.commit()
    db.close()
    return campaign_id


def test_list_campaigns():
    _seed_campaign()
    resp = client.get("/api/campaigns")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Campaign"
    assert data[0]["recipient_count"] == 5


def test_send_campaign_dispatches_tasks():
    """The endpoint dispatches background tasks and returns immediately."""
    campaign_id = _seed_campaign()
    with patch("app.tasks.send_single_email.delay") as mock_delay:
        resp = client.post(f"/api/campaigns/{campaign_id}/send")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "dispatched"
    assert data["total"] == 5
    assert mock_delay.call_count == 5


def test_campaign_status():
    campaign_id = _seed_campaign()
    resp = client.get(f"/api/campaigns/{campaign_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["sent"] == 0
