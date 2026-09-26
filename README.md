# Phase 2: Real-Time Progress Tracking

When work moves to the background, the HTTP response can no longer deliver the final result.
In this phase, we add client-side status polling so the user can track deliveries in real time.

---

## 🏃 Running Phase 2

Ensure Redis and Celery worker are running:
```bash
# Terminal 1 (Worker)
uv run celery -A app.celery_app:celery worker --loglevel=info --pool=solo

# Terminal 2 (FastAPI)
uv run uvicorn app.main:app --reload
```

---

## 🔍 What Changed?

Inspect the diff between Phase 1 and Phase 2:
```bash
git diff HEAD~1 app/templates/index.html
```

Notice:
* A delivery progress bar was added to the UI.
* When Send is clicked, the browser polls `GET /api/campaigns/{id}/status` every second.
* You see the progress bar fill up live (`45 / 200`, `120 / 200`...).

---

## ➡️ Next Step

Notice that some emails fail due to simulated network timeouts. How do we make delivery resilient?
```bash
git checkout phase-3-retry
```
