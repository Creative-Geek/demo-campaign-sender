# "The Overloaded Campaign Sender" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deliberately broken email-campaign-sending app, then fix it with Celery + Redis in a live-coding session — teaching junior interns *why* async task queues exist by letting them feel the pain first.

**Architecture:** A FastAPI web app with a single-page HTML frontend. Phase 1 is the "broken" synchronous version where clicking "Send Campaign" freezes the browser. Phase 2 introduces Celery + Redis to fix it incrementally: task offloading → progress tracking → retry logic → idempotency. Each fix is a small, self-contained code change.

**Tech Stack:** Python 3.11+, FastAPI, Celery, Redis, Jinja2 templates, SQLite (via SQLAlchemy), uv for dependency management

**Spec:** Brainstormed in conversation — no separate spec document. Requirements are inline below.

## Global Constraints

- Python 3.11+, all dependencies managed via `uv`
- Project lives at `m:\Others\Event-Driven-Presentation\demo-campaign-sender\`
- No frontend framework — vanilla HTML/CSS/JS, one page
- Email sending is **simulated** (random `time.sleep` + random failures), never real SMTP
- Redis must be runnable locally via Docker (`docker run redis`)
- The "broken" version must be fully functional (just slow/fragile) so interns can experience it
- Each fix phase is a separate git commit so interns can `git diff` between stages

---

## The Narrative Arc (What Interns Experience)

```
Phase 0: "The Broken App"
  → Click Send → browser freezes for 60+ seconds
  → Crash midway → some emails sent, no record of which
  → Click again → duplicates everywhere

Phase 1: "Offload to Celery"
  → Click Send → instant response → tasks process in background
  → Still no progress visibility, still no retry, still no dedup

Phase 2: "Add Progress Tracking"
  → Real-time progress bar shows tasks completing
  → Can see which emails succeeded/failed

Phase 3: "Add Retry Logic"  
  → Flaky email service no longer loses messages
  → Exponential backoff handles transient failures

Phase 4: "Add Idempotency"
  → Double-clicking Send doesn't send duplicates
  → Re-running a failed campaign resumes, doesn't restart
```

---

## File Structure

```
demo-campaign-sender/
├── pyproject.toml              # uv project config
├── README.md                   # Session guide for interns
├── docker-compose.yml          # Redis + (optional) Flower
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, routes
│   ├── models.py               # SQLAlchemy models (Campaign, Recipient, SendLog)
│   ├── database.py             # DB engine, session, init
│   ├── email_service.py        # Simulated email sender (sleep + random fail)
│   ├── tasks.py                # Celery tasks (added in Phase 1)
│   ├── celery_app.py           # Celery config (added in Phase 1)
│   └── templates/
│       └── index.html          # Single-page UI
├── seed.py                     # Seed script: creates a campaign with 200 recipients
└── tests/
    ├── __init__.py
    ├── test_email_service.py   # Tests for the simulated email service
    ├── test_models.py          # Tests for DB models
    ├── test_api.py             # Tests for API endpoints
    └── test_tasks.py           # Tests for Celery tasks (added in Phase 1)
```

---

## Task 1: Project Scaffold + Simulated Email Service

**Files:**
- Create: `demo-campaign-sender/pyproject.toml`
- Create: `demo-campaign-sender/app/__init__.py`
- Create: `demo-campaign-sender/app/email_service.py`
- Test: `demo-campaign-sender/tests/__init__.py`
- Test: `demo-campaign-sender/tests/test_email_service.py`

**Interfaces:**
- Consumes: Nothing (first task)
- Produces:
  - `send_email(to: str, subject: str, body: str) -> dict` — returns `{"status": "sent", "to": to}` or raises `EmailServiceError` on simulated failure. Takes 0.3–1.5s per call (simulated latency). Fails ~20% of the time.

- [ ] **Step 1: Create project with uv**

```bash
cd "m:\Others\Event-Driven-Presentation"
mkdir demo-campaign-sender
cd demo-campaign-sender
uv init
uv add fastapi uvicorn[standard] sqlalchemy aiofiles jinja2 celery[redis] redis
uv add --dev pytest pytest-asyncio httpx
```

- [ ] **Step 2: Write the failing test for email_service**

```python
# tests/test_email_service.py
import time
from unittest.mock import patch
from app.email_service import send_email, EmailServiceError


def test_send_email_returns_sent_status():
    """Successful send returns a dict with status='sent' and the recipient."""
    with patch("app.email_service.random.random", return_value=0.5):  # > 0.2 threshold = success
        with patch("app.email_service.time.sleep"):  # skip actual sleep in tests
            result = send_email("intern@example.com", "Hello", "Welcome aboard")
    assert result["status"] == "sent"
    assert result["to"] == "intern@example.com"


def test_send_email_raises_on_simulated_failure():
    """When random() returns below failure threshold, EmailServiceError is raised."""
    with patch("app.email_service.random.random", return_value=0.1):  # < 0.2 = fail
        with patch("app.email_service.time.sleep"):
            try:
                send_email("intern@example.com", "Hello", "Welcome aboard")
                assert False, "Should have raised EmailServiceError"
            except EmailServiceError:
                pass


def test_send_email_has_latency():
    """Without mocking sleep, send_email takes at least 0.2 seconds."""
    with patch("app.email_service.random.random", return_value=0.5):
        start = time.time()
        send_email("intern@example.com", "Hello", "Welcome aboard")
        elapsed = time.time() - start
    assert elapsed >= 0.2, f"Expected latency, got {elapsed:.3f}s"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd "m:\Others\Event-Driven-Presentation\demo-campaign-sender"
uv run pytest tests/test_email_service.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.email_service'`

- [ ] **Step 4: Implement email_service.py**

```python
# app/email_service.py
"""Simulated email service.

Every call sleeps for 0.3–1.5 seconds (simulating real SMTP latency)
and fails ~20% of the time (simulating a flaky mail provider).
"""

import random
import time


class EmailServiceError(Exception):
    """Raised when the simulated email service fails."""
    pass


def send_email(to: str, subject: str, body: str) -> dict:
    """Send a simulated email. Blocks for 0.3–1.5s. Fails ~20% of the time."""
    # Simulate network latency
    latency = 0.3 + random.random() * 1.2  # 0.3 to 1.5 seconds
    time.sleep(latency)

    # Simulate flaky service: ~20% failure rate
    if random.random() < 0.2:
        raise EmailServiceError(f"SMTP connection to {to} timed out (simulated)")

    return {"status": "sent", "to": to, "latency_ms": int(latency * 1000)}
```

```python
# app/__init__.py
# Campaign Sender Demo App
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_email_service.py -v
```

Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: project scaffold + simulated email service"
```

---

## Task 2: Database Models

**Files:**
- Create: `demo-campaign-sender/app/database.py`
- Create: `demo-campaign-sender/app/models.py`
- Test: `demo-campaign-sender/tests/test_models.py`

**Interfaces:**
- Consumes: Nothing
- Produces:
  - `get_db() -> Generator[Session]` — FastAPI dependency for DB sessions
  - `init_db() -> None` — creates all tables
  - `Campaign` model — fields: `id: int`, `name: str`, `subject: str`, `body: str`, `status: str` (draft/sending/sent/failed), `created_at: datetime`
  - `Recipient` model — fields: `id: int`, `campaign_id: int` (FK), `email: str`
  - `SendLog` model — fields: `id: int`, `campaign_id: int` (FK), `recipient_email: str`, `status: str` (pending/sent/failed), `error: str | None`, `idempotency_key: str` (unique), `sent_at: datetime | None`

- [ ] **Step 1: Write the failing test for models**

```python
# tests/test_models.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Campaign, Recipient, SendLog


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_create_campaign_with_recipients():
    session = _make_session()
    campaign = Campaign(name="Welcome Wave", subject="Hello!", body="Welcome to the team.")
    session.add(campaign)
    session.commit()

    r1 = Recipient(campaign_id=campaign.id, email="a@example.com")
    r2 = Recipient(campaign_id=campaign.id, email="b@example.com")
    session.add_all([r1, r2])
    session.commit()

    assert session.query(Recipient).filter_by(campaign_id=campaign.id).count() == 2


def test_send_log_idempotency_key_unique():
    session = _make_session()
    campaign = Campaign(name="Test", subject="S", body="B")
    session.add(campaign)
    session.commit()

    log1 = SendLog(
        campaign_id=campaign.id,
        recipient_email="a@example.com",
        status="sent",
        idempotency_key="campaign-1-a@example.com",
    )
    session.add(log1)
    session.commit()

    log2 = SendLog(
        campaign_id=campaign.id,
        recipient_email="a@example.com",
        status="sent",
        idempotency_key="campaign-1-a@example.com",  # duplicate key
    )
    session.add(log2)
    try:
        session.commit()
        assert False, "Should have raised IntegrityError"
    except Exception:
        session.rollback()


def test_campaign_default_status_is_draft():
    session = _make_session()
    campaign = Campaign(name="Test", subject="S", body="B")
    session.add(campaign)
    session.commit()
    assert campaign.status == "draft"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement database.py and models.py**

```python
# app/database.py
"""Database setup — SQLite for simplicity."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "sqlite:///./campaign_sender.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
```

```python
# app/models.py
"""Database models for the campaign sender."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft | sending | sent | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Recipient(Base):
    __tablename__ = "recipients"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    email = Column(String(320), nullable=False)


class SendLog(Base):
    __tablename__ = "send_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    recipient_email = Column(String(320), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending | sent | failed
    error = Column(Text, nullable=True)
    idempotency_key = Column(String(500), nullable=False, unique=True)
    sent_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_send_log_idempotency"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/database.py app/models.py tests/test_models.py
git commit -m "feat: database models — Campaign, Recipient, SendLog"
```

---

## Task 3: The Broken Synchronous API + Frontend (Phase 0)

This is the "broken app" the interns experience first. The entire point is that it's painfully, obviously broken.

**Files:**
- Create: `demo-campaign-sender/app/main.py`
- Create: `demo-campaign-sender/app/templates/index.html`
- Create: `demo-campaign-sender/seed.py`
- Test: `demo-campaign-sender/tests/test_api.py`

**Interfaces:**
- Consumes: `email_service.send_email()`, `models.Campaign`, `models.Recipient`, `models.SendLog`, `database.get_db()`, `database.init_db()`
- Produces:
  - `GET /` — serves the HTML page
  - `GET /api/campaigns` — returns list of campaigns with recipient count
  - `POST /api/campaigns/{id}/send` — **THE BROKEN ENDPOINT**: loops through all recipients synchronously, sends each email one-by-one inside the request. Returns only after ALL emails are sent (or it crashes).
  - `GET /api/campaigns/{id}/status` — returns send progress (how many sent/failed/pending)
  - `seed.py` — populates DB with 1 campaign + 200 recipients

- [ ] **Step 1: Write API tests**

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from unittest.mock import patch

from app.database import Base, get_db
from app.main import app
from app.models import Campaign, Recipient


# Use in-memory SQLite for tests
test_engine = create_engine("sqlite:///:memory:")
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


def _seed_campaign():
    db = TestSession()
    c = Campaign(name="Test Campaign", subject="Hi", body="Hello there")
    db.add(c)
    db.commit()
    for i in range(5):  # small count for tests
        db.add(Recipient(campaign_id=c.id, email=f"user{i}@example.com"))
    db.commit()
    db.close()
    return c.id


def test_list_campaigns():
    _seed_campaign()
    resp = client.get("/api/campaigns")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Campaign"
    assert data[0]["recipient_count"] == 5


def test_send_campaign_synchronously():
    """The broken endpoint should send all emails synchronously and return results."""
    campaign_id = _seed_campaign()
    with patch("app.main.send_email") as mock_send:
        mock_send.return_value = {"status": "sent", "to": "test@example.com"}
        resp = client.post(f"/api/campaigns/{campaign_id}/send")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["sent"] + data["failed"] == 5


def test_campaign_status():
    campaign_id = _seed_campaign()
    resp = client.get(f"/api/campaigns/{campaign_id}/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["sent"] == 0  # nothing sent yet
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_api.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement main.py**

```python
# app/main.py
"""FastAPI app — Phase 0: Everything is synchronous and broken."""

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.email_service import send_email, EmailServiceError
from app.models import Campaign, Recipient, SendLog

app = FastAPI(title="Campaign Sender (Broken Edition)")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def home():
    with open("app/templates/index.html") as f:
        return f.read()


@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    result = []
    for c in campaigns:
        count = db.query(Recipient).filter_by(campaign_id=c.id).count()
        result.append({
            "id": c.id,
            "name": c.name,
            "subject": c.subject,
            "status": c.status,
            "recipient_count": count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return result


@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign_sync(campaign_id: int, db: Session = Depends(get_db)):
    """THE BROKEN ENDPOINT.

    Sends every email one-by-one inside the HTTP request.
    The browser freezes until ALL emails are processed.
    If this crashes halfway, some emails are sent but there's no record.
    No idempotency — hitting this twice sends duplicates.
    """
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    campaign.status = "sending"
    db.commit()

    recipients = db.query(Recipient).filter_by(campaign_id=campaign_id).all()

    sent = 0
    failed = 0

    for recipient in recipients:
        try:
            send_email(
                to=recipient.email,
                subject=campaign.subject,
                body=campaign.body,
            )
            # Log success
            log = SendLog(
                campaign_id=campaign_id,
                recipient_email=recipient.email,
                status="sent",
                idempotency_key=f"{campaign_id}-{recipient.email}",
                sent_at=datetime.now(timezone.utc),
            )
            db.add(log)
            db.commit()
            sent += 1
        except EmailServiceError as e:
            log = SendLog(
                campaign_id=campaign_id,
                recipient_email=recipient.email,
                status="failed",
                error=str(e),
                idempotency_key=f"{campaign_id}-{recipient.email}",
            )
            db.add(log)
            db.commit()
            failed += 1

    campaign.status = "sent" if failed == 0 else "failed"
    db.commit()

    return {"total": len(recipients), "sent": sent, "failed": failed}


@app.get("/api/campaigns/{campaign_id}/status")
def campaign_status(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    total = db.query(Recipient).filter_by(campaign_id=campaign_id).count()
    sent = db.query(SendLog).filter_by(campaign_id=campaign_id, status="sent").count()
    failed = db.query(SendLog).filter_by(campaign_id=campaign_id, status="failed").count()

    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "total": total,
        "sent": sent,
        "failed": failed,
        "pending": total - sent - failed,
    }
```

- [ ] **Step 4: Create the frontend (index.html)**

A single-page HTML file with:
- A list of campaigns with "Send" buttons
- A status display showing sent/failed/pending counts
- A visible timer that starts counting when "Send" is clicked (so interns SEE the browser freeze)
- Minimal styling — clean, functional, not pretty

```html
<!-- app/templates/index.html -->
<!-- Full implementation: a simple vanilla HTML/JS page with
     fetch() calls to the API endpoints, a campaign list,
     a "Send Campaign" button, and a status poller.
     Key visual: a running clock/timer that FREEZES when the
     synchronous endpoint blocks, making the problem visceral. -->
```

*(Full HTML ~150 lines — implementer builds this with: campaign list, send button, elapsed-time counter, status display, and polling logic.)*

- [ ] **Step 5: Create seed.py**

```python
# seed.py
"""Seed the database with a test campaign and 200 recipients."""

from app.database import init_db, SessionLocal
from app.models import Campaign, Recipient

def seed():
    init_db()
    db = SessionLocal()

    # Clear existing data
    db.query(Recipient).delete()
    db.query(Campaign).delete()
    db.commit()

    campaign = Campaign(
        name="Q3 Product Launch Announcement",
        subject="Exciting News: Our New Platform is Live!",
        body="Hi there! We're thrilled to announce the launch of our new platform...",
    )
    db.add(campaign)
    db.commit()

    # Generate 200 fake recipients
    for i in range(200):
        db.add(Recipient(
            campaign_id=campaign.id,
            email=f"employee{i:03d}@bigcorp.example.com",
        ))
    db.commit()
    db.close()
    print(f"Seeded campaign '{campaign.name}' with 200 recipients.")

if __name__ == "__main__":
    seed()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_api.py -v
```

Expected: 4 PASS

- [ ] **Step 7: Manual smoke test — experience the broken app**

```bash
uv run python seed.py
uv run uvicorn app.main:app --reload
# Open http://localhost:8000, click "Send Campaign", watch the browser hang
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: Phase 0 — the broken synchronous campaign sender"
```

---

## Task 4: Phase 1 — Offload to Celery

This is the first fix. The send endpoint dispatches individual Celery tasks instead of sending synchronously.

**Files:**
- Create: `demo-campaign-sender/app/celery_app.py`
- Create: `demo-campaign-sender/app/tasks.py`
- Create: `demo-campaign-sender/docker-compose.yml`
- Modify: `demo-campaign-sender/app/main.py` — change `send_campaign_sync` to dispatch tasks
- Test: `demo-campaign-sender/tests/test_tasks.py`

**Interfaces:**
- Consumes: `email_service.send_email()`, `models.SendLog`, `database.SessionLocal`
- Produces:
  - `send_single_email.delay(campaign_id: int, recipient_email: str, subject: str, body: str)` — Celery task that sends one email and logs the result
  - `POST /api/campaigns/{id}/send` now returns instantly with `{"status": "dispatched", "task_count": N}`

- [ ] **Step 1: Write the failing test for the Celery task**

```python
# tests/test_tasks.py
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Campaign, Recipient, SendLog


test_engine = create_engine("sqlite:///:memory:")
TestSession = sessionmaker(bind=test_engine)


def setup_function():
    Base.metadata.create_all(test_engine)


def teardown_function():
    Base.metadata.drop_all(test_engine)


def test_send_single_email_task_logs_success():
    """The Celery task should call send_email and log a successful send."""
    db = TestSession()
    c = Campaign(name="Test", subject="Hi", body="Body")
    db.add(c)
    db.commit()
    campaign_id = c.id
    db.close()

    with patch("app.tasks.SessionLocal", TestSession):
        with patch("app.tasks.send_email") as mock_send:
            mock_send.return_value = {"status": "sent", "to": "test@example.com"}
            from app.tasks import send_single_email
            send_single_email(campaign_id, "test@example.com", "Hi", "Body")

    db = TestSession()
    log = db.query(SendLog).filter_by(campaign_id=campaign_id).first()
    assert log is not None
    assert log.status == "sent"
    assert log.recipient_email == "test@example.com"
    db.close()


def test_send_single_email_task_logs_failure():
    """When send_email raises, the task should log a failure."""
    db = TestSession()
    c = Campaign(name="Test", subject="Hi", body="Body")
    db.add(c)
    db.commit()
    campaign_id = c.id
    db.close()

    with patch("app.tasks.SessionLocal", TestSession):
        with patch("app.tasks.send_email") as mock_send:
            from app.email_service import EmailServiceError
            mock_send.side_effect = EmailServiceError("Timeout")
            from app.tasks import send_single_email
            send_single_email(campaign_id, "fail@example.com", "Hi", "Body")

    db = TestSession()
    log = db.query(SendLog).filter_by(campaign_id=campaign_id).first()
    assert log is not None
    assert log.status == "failed"
    assert "Timeout" in log.error
    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_tasks.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.tasks'`

- [ ] **Step 3: Create docker-compose.yml for Redis**

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

- [ ] **Step 4: Implement celery_app.py**

```python
# app/celery_app.py
"""Celery application configuration."""

from celery import Celery

celery = Celery(
    "campaign_sender",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/1",
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
)
```

- [ ] **Step 5: Implement tasks.py**

```python
# app/tasks.py
"""Celery tasks for sending emails."""

from datetime import datetime, timezone

from app.celery_app import celery
from app.database import SessionLocal
from app.email_service import send_email, EmailServiceError
from app.models import SendLog


@celery.task(name="send_single_email")
def send_single_email(campaign_id: int, recipient_email: str, subject: str, body: str):
    """Send a single email and log the result to the database."""
    db = SessionLocal()
    try:
        send_email(to=recipient_email, subject=subject, body=body)
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="sent",
            idempotency_key=f"{campaign_id}-{recipient_email}",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
    except EmailServiceError as e:
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="failed",
            error=str(e),
            idempotency_key=f"{campaign_id}-{recipient_email}",
        )
        db.add(log)
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 6: Modify main.py — replace sync send with task dispatch**

Change the `send_campaign_sync` endpoint to dispatch Celery tasks:

```python
# In app/main.py — replace the send_campaign_sync function with:

@app.post("/api/campaigns/{campaign_id}/send")
def send_campaign(campaign_id: int, db: Session = Depends(get_db)):
    """FIXED: Dispatches a Celery task per recipient and returns immediately."""
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    campaign.status = "sending"
    db.commit()

    recipients = db.query(Recipient).filter_by(campaign_id=campaign_id).all()

    for recipient in recipients:
        from app.tasks import send_single_email
        send_single_email.delay(
            campaign_id=campaign_id,
            recipient_email=recipient.email,
            subject=campaign.subject,
            body=campaign.body,
        )

    return {"status": "dispatched", "task_count": len(recipients)}
```

Also add the import at the top of main.py — but the actual `from app.tasks import` is done inside the function to avoid circular imports.

- [ ] **Step 7: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All PASS (API test for send needs updating since response shape changed — update `test_send_campaign_synchronously` to mock `send_single_email.delay` and assert the new response shape)

- [ ] **Step 8: Manual smoke test — experience the fix**

```bash
# Terminal 1: Redis
docker compose up -d

# Terminal 2: Celery worker
uv run celery -A app.celery_app:celery worker --loglevel=info --pool=solo

# Terminal 3: FastAPI
uv run python seed.py
uv run uvicorn app.main:app --reload

# Open http://localhost:8000, click "Send Campaign"
# INSTANT response! Watch Celery terminal process tasks in background.
```

- [ ] **Step 9: Commit**

```bash
git add .
git commit -m "feat: Phase 1 — offload email sending to Celery tasks"
```

---

## Task 5: Phase 2 — Progress Tracking

**Files:**
- Modify: `demo-campaign-sender/app/templates/index.html` — add progress bar + polling
- The API already has `GET /api/campaigns/{id}/status` from Task 3

**Interfaces:**
- Consumes: `GET /api/campaigns/{id}/status`
- Produces: Real-time progress bar in the UI that polls every second

- [ ] **Step 1: Update index.html with progress polling**

Add JavaScript that:
1. After clicking "Send", starts a `setInterval` that polls `/api/campaigns/{id}/status` every second
2. Renders a progress bar: `(sent + failed) / total * 100%`
3. Shows counts: "142/200 sent, 8 failed, 50 pending"
4. Stops polling when `pending == 0`

- [ ] **Step 2: Manual smoke test**

```bash
# With Redis + Celery + FastAPI running:
# Open http://localhost:8000, click Send, watch the progress bar fill in real-time
```

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "feat: Phase 2 — real-time progress bar via status polling"
```

---

## Task 6: Phase 3 — Retry Logic

**Files:**
- Modify: `demo-campaign-sender/app/tasks.py` — add Celery retry config
- Modify: `demo-campaign-sender/tests/test_tasks.py` — add retry test

**Interfaces:**
- Consumes: `send_single_email` task
- Produces: `send_single_email` with `autoretry_for=(EmailServiceError,)`, `max_retries=3`, `retry_backoff=True`

- [ ] **Step 1: Write the failing test for retry behavior**

```python
# Add to tests/test_tasks.py

def test_task_has_retry_configuration():
    """The task should be configured to retry on EmailServiceError."""
    from app.tasks import send_single_email
    # Celery stores retry config on the task object
    assert send_single_email.max_retries == 3
    assert send_single_email.autoretry_for == (EmailServiceError,)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tasks.py::test_task_has_retry_configuration -v
```

Expected: FAIL — task doesn't have retry config yet

- [ ] **Step 3: Add retry config to the task decorator**

```python
# In app/tasks.py — update the decorator:

from app.email_service import send_email, EmailServiceError

@celery.task(
    name="send_single_email",
    autoretry_for=(EmailServiceError,),
    max_retries=3,
    retry_backoff=True,       # exponential: 1s, 2s, 4s
    retry_backoff_max=30,
)
def send_single_email(campaign_id: int, recipient_email: str, subject: str, body: str):
    # ... same body, but now REMOVE the try/except around send_email
    # Let EmailServiceError propagate so Celery can retry it
    db = SessionLocal()
    try:
        send_email(to=recipient_email, subject=subject, body=body)
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="sent",
            idempotency_key=f"{campaign_id}-{recipient_email}",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
    finally:
        db.close()
```

Also add an `on_failure` handler to log final failures after all retries are exhausted.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_tasks.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: Phase 3 — retry with exponential backoff on flaky sends"
```

---

## Task 7: Phase 4 — Idempotency

**Files:**
- Modify: `demo-campaign-sender/app/tasks.py` — check idempotency key before sending
- Modify: `demo-campaign-sender/tests/test_tasks.py` — add idempotency test

**Interfaces:**
- Consumes: `SendLog.idempotency_key`
- Produces: `send_single_email` checks if a `SendLog` with the same idempotency key and `status="sent"` already exists; if so, skips without re-sending

- [ ] **Step 1: Write the failing test for idempotency**

```python
# Add to tests/test_tasks.py

def test_duplicate_send_is_skipped():
    """If a SendLog with status='sent' exists for this key, the task should skip."""
    db = TestSession()
    c = Campaign(name="Test", subject="Hi", body="Body")
    db.add(c)
    db.commit()
    campaign_id = c.id

    # Pre-insert a "sent" log
    existing = SendLog(
        campaign_id=campaign_id,
        recipient_email="already@example.com",
        status="sent",
        idempotency_key=f"{campaign_id}-already@example.com",
    )
    db.add(existing)
    db.commit()
    db.close()

    with patch("app.tasks.SessionLocal", TestSession):
        with patch("app.tasks.send_email") as mock_send:
            from app.tasks import send_single_email
            send_single_email(campaign_id, "already@example.com", "Hi", "Body")

    # send_email should NOT have been called
    mock_send.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_tasks.py::test_duplicate_send_is_skipped -v
```

Expected: FAIL — `send_email` is still called

- [ ] **Step 3: Add idempotency check to the task**

```python
# In app/tasks.py — add check at the top of send_single_email:

@celery.task(
    name="send_single_email",
    autoretry_for=(EmailServiceError,),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=30,
)
def send_single_email(campaign_id: int, recipient_email: str, subject: str, body: str):
    """Send one email. Idempotent: skips if already sent successfully."""
    db = SessionLocal()
    try:
        idempotency_key = f"{campaign_id}-{recipient_email}"

        # IDEMPOTENCY CHECK: skip if already sent
        existing = db.query(SendLog).filter_by(
            idempotency_key=idempotency_key, status="sent"
        ).first()
        if existing:
            return {"skipped": True, "reason": "already sent"}

        send_email(to=recipient_email, subject=subject, body=body)
        log = SendLog(
            campaign_id=campaign_id,
            recipient_email=recipient_email,
            status="sent",
            idempotency_key=idempotency_key,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        return {"status": "sent", "to": recipient_email}
    finally:
        db.close()
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 5: Manual smoke test — double-click doesn't duplicate**

```bash
# With everything running, click "Send Campaign" twice quickly
# Second batch of tasks should all skip ("already sent")
# Check Celery logs for "skipped" messages
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "feat: Phase 4 — idempotency check prevents duplicate sends"
```

---

## Task 8: README + Session Guide

**Files:**
- Create: `demo-campaign-sender/README.md`

**Interfaces:**
- Consumes: Everything above
- Produces: A README that serves as the live-coding session guide

- [ ] **Step 1: Write the README**

The README should contain:
1. **What this is** — a deliberately broken campaign sender used to teach async task processing
2. **Prerequisites** — Python 3.11+, Docker, uv
3. **Quick start** — clone, `uv sync`, `docker compose up -d`, seed, run
4. **The experience** — "Click Send. Watch it freeze. Now let's fix it."
5. **Fix 1: Celery** — what changes, why, how to run the worker
6. **Fix 2: Progress** — how polling works
7. **Fix 3: Retry** — what `autoretry_for` does
8. **Fix 4: Idempotency** — the key check pattern
9. **Running tests** — `uv run pytest`

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: session guide README"
```

---

## Self-Review

**Spec coverage:**
- Broken synchronous version that freezes the browser: Task 3 ✓
- Celery + Redis fix: Task 4 ✓
- Progress tracking: Task 5 ✓
- Retry with backoff: Task 6 ✓
- Idempotency: Task 7 ✓
- Session guide: Task 8 ✓
- No overlap with presentation examples (no warehouse, satellite, incident bot): ✓

**Placeholder scan:** No TBD/TODO items except Task 5's HTML update (which is intentionally left as a description since the exact HTML depends on Phase 0's template) and Task 3's index.html (same — implementer builds the full HTML).

**Type consistency:** `send_single_email(campaign_id: int, recipient_email: str, subject: str, body: str)` — consistent across Tasks 4, 6, 7. `SendLog.idempotency_key` format `"{campaign_id}-{recipient_email}"` — consistent across Tasks 2, 3, 4, 7.
