"""ashgrove command line.

ashgrove dev                 run all six services locally (no Docker needed)
ashgrove serve <service>     run one service (what each container does)
ashgrove reset [service]     re-create the seeded data
ashgrove export <dir>        write every table to CSV (for data-onboarding work)
"""

from __future__ import annotations

import argparse
import csv
import importlib
import os
import sqlite3
import threading
import time
from pathlib import Path

from . import SERVICES


def _module(name: str):
    if name not in SERVICES:
        raise SystemExit(f"Unknown service {name!r}. Choose from: {', '.join(SERVICES)}")
    return importlib.import_module(f"ashgrove.{name}")


def serve(name: str, host: str, port: int | None) -> None:
    import uvicorn

    uvicorn.run(_module(name).app, host=host, port=port or int(os.getenv("PORT", SERVICES[name])), log_level="info")


def dev(host: str) -> None:
    import uvicorn

    servers = []
    for name, port in SERVICES.items():
        config = uvicorn.Config(_module(name).app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        threading.Thread(target=server.run, daemon=True).start()
        servers.append((name, port, server))
    time.sleep(1.0)
    print("Ashgrove sandbox is running:")
    for name, port, _ in servers:
        print(f"  {name:<9} http://{host}:{port}/docs")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        for *_, server in servers:
            server.should_exit = True


def reset(name: str | None) -> None:
    for svc in [name] if name else SERVICES:
        _module(svc).store.reset()
        print(f"reset {svc}")


def export(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for svc in SERVICES:
        store = _module(svc).store
        with store.connect():
            pass  # creates and seeds if missing
        conn = sqlite3.connect(store.path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            cur = conn.execute(f"SELECT * FROM {table}")  # noqa: S608 - table names come from sqlite_master
            path = out / f"{svc}__{table}.csv"
            with path.open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow([d[0] for d in cur.description])
                w.writerows(cur.fetchall())
        conn.close()
    print(f"exported CSV files to {out}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="ashgrove", description="The Ashgrove Group sandbox")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dev", help="run all services locally")
    d.add_argument("--host", default="127.0.0.1")
    s = sub.add_parser("serve", help="run one service")
    s.add_argument("service", choices=list(SERVICES))
    s.add_argument("--host", default="0.0.0.0")  # noqa: S104 - containers listen on all interfaces
    s.add_argument("--port", type=int)
    r = sub.add_parser("reset", help="re-create seeded data")
    r.add_argument("service", nargs="?", choices=list(SERVICES))
    e = sub.add_parser("export", help="export all tables to CSV")
    e.add_argument("out", type=Path)
    a = p.parse_args(argv)
    if a.cmd == "dev":
        dev(a.host)
    elif a.cmd == "serve":
        serve(a.service, a.host, a.port)
    elif a.cmd == "reset":
        reset(a.service)
    else:
        export(a.out)


if __name__ == "__main__":
    main()
