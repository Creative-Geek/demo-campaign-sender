# Phase 3: Automatic Retries with Exponential Backoff

In distributed systems, networks flake.
In this phase, we configure Celery's built-in automatic retries with exponential backoff on transient errors.

---

## 🏃 Running Phase 3

```bash
# Terminal 1 (Worker)
uv run celery -A app.celery_app:celery worker --loglevel=info --pool=solo

# Terminal 2 (FastAPI)
uv run uvicorn app.main:app --reload
```

---

## 🔍 What Changed?

Inspect the diff between Phase 2 and Phase 3:
```bash
git diff HEAD~1 -- app/tasks.py
```

Notice:
* `autoretry_for=(EmailServiceError,)`: Automatically retries on network timeout.
* `max_retries=3`: Gives up after 3 failed attempts.
* `retry_backoff=True`: Waits exponentially longer between attempts (1s, 2s, 4s...).
* Watch the Celery terminal: failed emails pause and retry automatically without losing messages.

---

## ➡️ Next Step

What happens if an impatient user double-clicks the Send button?
```bash
git checkout phase-4-idempotency
```
