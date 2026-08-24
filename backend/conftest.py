"""
Root conftest for the backend test suite.

Celery reads CELERY_BROKER_URL / CELERY_RESULT_BACKEND directly from
os.environ (env-vars win over Django settings).  We must patch those env-vars
*before* the Celery app object finalises its config, then push the values in
directly so there is no network I/O during tests.
"""
import os


def pytest_configure(config):
    """
    Called very early — before Django setup and before any imports of
    config.celery.  Neutralise the env-vars that would otherwise make Celery
    connect to Redis.
    """
    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"


def pytest_sessionstart(session):
    """
    After Django is fully initialised, force-push test-safe values into the
    Celery app object, overriding whatever it cached during module import.
    """
    try:
        from config.celery import app  # noqa: PLC0415

        app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
            result_backend="cache+memory://",
            broker_url="memory://",
            task_ignore_result=True,
        )
    except Exception:
        pass  # Django not yet ready — pytest_configure handled the env-vars
