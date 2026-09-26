"""Background-service lifecycle; importing this module starts nothing."""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from broker_config import settings
from domains.ibkr import get_ibkr_service
from domains.trading import auto_import
from services import interruption_cause, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background services around the app lifecycle."""
    # Work out WHY any interrupted scan run died, off the event loop. It reads
    # the Windows event log, which is only up at a real service start — never at
    # the import-time boot migrations, where the reconcile itself can run inside
    # a dying Windows session. Best-effort by construction: an unresolved row
    # simply stays pending for the next start, so startup never waits on it.
    asyncio.get_running_loop().run_in_executor(None, interruption_cause.resolve_pending)
    auto_import.start_writer()
    scheduler.start_scheduler()
    svc = get_ibkr_service()
    svc.add_execution_listener(auto_import.submit_execution)
    if settings.ibkr_auto_connect:
        try:
            svc.start()
        except Exception:
            logging.exception("Failed to start IBKR service")
    try:
        yield
    finally:
        _stop_services(svc)


def _stop_services(svc) -> None:
    for label, stop in (
        ("IBKR service", svc.stop),
        ("auto-import writer", auto_import.stop_writer),
        ("scan scheduler", scheduler.stop_scheduler),
    ):
        try:
            stop()
        except Exception:
            logging.exception("Failed to stop %s", label)


