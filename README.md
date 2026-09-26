# Phase 4: Idempotency (Preventing Duplicate Side Effects)

If a user clicks Send twice, or if a network retry delivers a task duplicate, recipients could receive multiple emails.
In this phase, we add a pre-send database check to guarantee idempotency.

---

## 🏃 Running Phase 4

```bash
# Terminal 1 (Worker)
uv run celery -A app.celery_app:celery worker --loglevel=info --pool=solo

# Terminal 2 (FastAPI)
uv run uvicorn app.main:app --reload
```

---

## 🔍 What Changed?

Inspect the diff between Phase 3 and Phase 4:
```bash
git diff HEAD~1 -- app/tasks.py
```

Notice:
* Before calling `send_email()`, the worker queries `SendLog` for `idempotency_key = f"{campaign_id}-{email}"`.
* If a record marked `status="sent"` already exists, it returns immediately without re-sending.
* Try clicking Send twice rapidly: the second batch skips in milliseconds with **zero duplicate emails**.

---

## 🧪 Full Test Suite

Verify the complete system:
```bash
uv run pytest -v
```
