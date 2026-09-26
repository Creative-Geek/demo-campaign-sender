# Phase 0: The Broken Synchronous App

Welcome to the Event-Driven Systems lab!

This project demonstrates what happens when an application performs slow, variable-latency operations directly inside a synchronous HTTP request.

---

## 🧭 How to Navigate This Workshop

This repository is organized into progressive git branches. Each branch represents one fix stage:
* **`phase-0-broken`** *(You are here)*: Synchronous baseline (freezes, no queue)
* **`phase-1-celery`**: Offloads tasks to Celery + Redis
* **`phase-2-progress`**: Adds real-time progress polling
* **`phase-3-retry`**: Adds automatic retries with exponential backoff
* **`phase-4-idempotency`**: Adds idempotency checks to prevent duplicate sends

---

## 🏃 Running Phase 0

> **Note:** Docker and Redis are **NOT** needed for Phase 0. Everything runs locally with SQLite and FastAPI.

```bash
# 1. Install dependencies
uv sync

# 2. Seed database with 200 recipients
uv run python seed.py

# 3. Start the FastAPI server
uv run uvicorn app.main:app --reload
```

Open **`http://localhost:8000`** in your browser.

---

## 💥 The Experiment

1. Click **"Send Campaign Now (Synchronous)"**.
2. Observe:
   * The live timer starts counting up.
   * The browser tab's loading spinner hangs.
   * Sending 200 emails at ~0.9s each takes approximately **3 minutes**.
   * After 60s, the browser will likely time out, but the server continues running in the background.

---

## ➡️ Next Step

To see how we solve the browser freeze by moving email delivery to a background queue:
```bash
git checkout phase-1-celery
```
