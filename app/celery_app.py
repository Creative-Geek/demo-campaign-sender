# app/celery_app.py
"""Celery application configuration."""

from celery import Celery

celery = Celery(
    "campaign_sender",
    broker="redis://localhost:6379/0", # redis database 0 for task queue
    backend="redis://localhost:6379/1", # redis database 1 for task results
    include=["app.tasks"], # register task modules with the worker
)

celery.conf.update(
    task_serializer="json", # serialize task payloads as json
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True, # track when task begins execution
)
