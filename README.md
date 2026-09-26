# Phase 1: Celery Task Offloading

In this phase, we decouple accepting work from executing work.
Instead of sending emails inside the HTTP request loop, we push each recipient as an asynchronous task to a Redis queue.

---

## 🐳 Prerequisites

Starting from Phase 1, **Docker** is required to run the Redis message broker.

```bash
# 1. Start Redis broker
docker compose up -d

# 2. Start Celery worker in Terminal 1
uv run celery -A app.celery_app:celery worker --loglevel=info --pool=solo

# 3. Start FastAPI server in Terminal 2
uv run uvicorn app.main:app --reload
```

Open **`http://localhost:8000`** in your browser.

---

## 🔍 What Changed?

Inspect the diff between Phase 0 and Phase 1:
```bash
git diff HEAD~1 app/main.py
```

Notice:
* The synchronous `send_email(...)` call in `app/main.py` was replaced with `send_single_email.delay(...)`.
* The HTTP request returns in **< 50 milliseconds**.
* The background Celery worker picks up and processes tasks independently.

---

## ➡️ Next Step

The request returns instantly, but how does the user see delivery progress?
```bash
git checkout phase-2-progress
```
