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
