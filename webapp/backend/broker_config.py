"""Runtime **broker** configuration for the Chrollo backend (IBKR mode/client/port).

Imported as ``broker_config`` — deliberately NOT named ``config``. The backend
service runs with cwd = ``webapp/backend``, so a module named ``config`` here
would shadow the repo-root ``config`` *screener* package for everything the
backend imports (including ``core``), which previously crashed the service boot.
Keeping this name distinct lets both configs coexist: ``config`` = screener,
``broker_config`` = broker.

``settings`` is a shared mutable object so the IBKR mode/client can be flipped at
runtime via ``set_mode()`` / ``set_client()``. Consumers must read
``broker_config.settings.<field>`` each time they need a value (don't cache into
locals at import time).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Mode = Literal["paper", "live"]
Client = Literal["tws", "gateway"]

# (client, mode) → default port
PORT_MAP: dict[tuple[Client, Mode], int] = {
    ("tws", "paper"): 7497,
    ("tws", "live"): 7496,
    ("gateway", "paper"): 4002,
    ("gateway", "live"): 4001,
}


def _default_port(client: Client, mode: Mode) -> int:
    return PORT_MAP[(client, mode)]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    ibkr_host: str
    ibkr_port: int
    ibkr_client_id: int
    ibkr_mode: Mode
    ibkr_client: Client
    ibkr_auto_connect: bool
    # Was the port set explicitly via IBKR_PORT env? If so, set_mode()/set_client()
    # preserve it; otherwise we swap to the mode/client default port when either changes.
    ibkr_port_is_explicit: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        mode_raw = os.environ.get("IBKR_MODE", "live").strip().lower()
        mode: Mode = "paper" if mode_raw == "paper" else "live"

        client_raw = os.environ.get("IBKR_CLIENT", "gateway").strip().lower()
        client: Client = "tws" if client_raw == "tws" else "gateway"

        port_env = os.environ.get("IBKR_PORT")
        port = int(port_env) if port_env else _default_port(client, mode)

        return cls(
            ibkr_host=os.environ.get("IBKR_HOST", "127.0.0.1"),
            ibkr_port=port,
            ibkr_client_id=int(os.environ.get("IBKR_CLIENT_ID", "137")),
            ibkr_mode=mode,
            ibkr_client=client,
            ibkr_auto_connect=_env_bool("IBKR_AUTO_CONNECT", False),
            ibkr_port_is_explicit=bool(port_env),
        )


settings = Settings.from_env()


def is_live_mode() -> bool:
    return settings.ibkr_mode == "live"


def set_mode(mode: Mode) -> None:
    """Switch runtime mode. Updates the port to the (client, mode) default unless
    the user pinned a port via IBKR_PORT at startup."""
    if mode not in ("paper", "live"):
        raise ValueError(f"invalid mode: {mode!r}")
    settings.ibkr_mode = mode
    if not settings.ibkr_port_is_explicit:
        settings.ibkr_port = _default_port(settings.ibkr_client, mode)


def set_client(client: Client) -> None:
    """Switch between TWS and IB Gateway. Updates the port to the (client, mode)
    default unless the user pinned a port via IBKR_PORT at startup."""
    if client not in ("tws", "gateway"):
        raise ValueError(f"invalid client: {client!r}")
    settings.ibkr_client = client
    if not settings.ibkr_port_is_explicit:
        settings.ibkr_port = _default_port(client, settings.ibkr_mode)
