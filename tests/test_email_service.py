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
