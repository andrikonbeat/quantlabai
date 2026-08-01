"""Mock SQX HTTP server for demo and testing without a real SQX license."""

from __future__ import annotations

import csv
import json
import logging
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MOCK_PORT = 5050
_MOCK_HOST = "127.0.0.1"


class MockSQXHandler(BaseHTTPRequestHandler):
    """HTTP handler that simulates SQX CLI commands.

    ``_mode`` is class-level so every per-request handler instance observes
    the same configuration:

    - ``normal`` (default): full campaign lifecycle — starts, makes progress,
      and completes on its own.
    - ``rejection``: simulates a zero-acceptance run — the generated count
      grows on every status poll while the databank record count stays at 0,
      and the campaign never completes until an explicit ``action=stop``.
    """

    _campaigns: dict[str, dict[str, Any]] = {}
    _lock = threading.Lock()
    _mode: str = "normal"
    _export_dir = Path("/tmp/sqx-mock-exports")
    _export_dir.mkdir(parents=True, exist_ok=True)

    def log_message(self, format, *args):
        logger.debug(format, *args)

    def _send_text(self, text: str, status: int = 200):
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(text.encode("utf-8"))
            self.wfile.flush()
        except Exception as exc:
            logger.debug("Mock send failed: %s", exc)

    def _parse_command(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else ""
        if body.startswith("cmd="):
            import urllib.parse
            return urllib.parse.unquote(body[4:])
        return body

    def do_GET(self):
        try:
            cmd = ""
            if self.path.startswith("/call?"):
                import urllib.parse
                qs = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(qs)
                cmd = params.get("cmd", [""])[0]
            self._handle_command(cmd)
        except Exception as exc:
            logger.debug("Mock GET error: %s", exc, exc_info=True)
            try:
                self._send_text(f"Mock error: {exc}", status=500)
            except Exception:
                pass

    def do_POST(self):
        try:
            cmd = self._parse_command()
            self._handle_command(cmd)
        except Exception as exc:
            logger.debug("Mock POST error: %s", exc, exc_info=True)
            try:
                self._send_text(f"Mock error: {exc}", status=500)
            except Exception:
                pass

    def _handle_command(self, cmd: str):
        if not cmd:
            return self._send_text("Missing command.", status=400)

        parts = cmd.split()
        if parts[0] in ("-h", "-help"):
            return self._send_text(
                "Usage: sqcli.exe\n-project Manage projects.\n-databank Manage databanks."
            )

        if parts[0] == "-project":
            action = parts[1] if len(parts) > 1 else ""
            name = ""
            for p in parts[2:]:
                if p.startswith("name="):
                    name = p[5:]
            if action == "action=list":
                return self._send_text(
                    "List of available projects\n--------------------------------------------------\nBuilder\nOptimizer\nRetester\n"
                )
            if action == "action=loadconfig":
                with MockSQXHandler._lock:
                    MockSQXHandler._campaigns[name] = {"status": "loaded", "progress": 0}
                return self._send_text(f"Project loaded '{name}'.\n")
            if action == "action=start":
                with MockSQXHandler._lock:
                    MockSQXHandler._campaigns[name] = {
                        "status": "running",
                        "progress": 0,
                        "generated": 0,
                    }
                threading.Thread(
                    target=self._simulate_campaign, args=(name,), daemon=True
                ).start()
                return self._send_text(
                    f"Project is running on the background. To get project status use\n-project action=status name={name}\n"
                )
            if action == "action=status":
                with MockSQXHandler._lock:
                    camp = MockSQXHandler._campaigns.get(name, {"status": "not found", "progress": 0})
                    # Rejection mode: grow the generated count on each poll.
                    if (
                        MockSQXHandler._mode == "rejection"
                        and camp.get("status") == "running"
                    ):
                        camp["generated"] = camp.get("generated", 0) + 10
                text = f"Status of project {name}\n--------------------------------------------------\n"
                if camp.get("status") == "completed":
                    text += "Status: completed\n"
                    text += "Strategies generated                           42\n"
                    text += "Running time so far                          4 s.\n"
                    text += "In databank                                      3\n"
                elif camp.get("status") == "running":
                    if MockSQXHandler._mode == "rejection":
                        text += f"Strategies generated                            {camp.get('generated', 0)}\n"
                        text += "Running time so far                          2 s.\n"
                        text += "In databank                                      0\n"
                    else:
                        text += "Strategies generated                          12\n"
                        text += "Running time so far                          2 s.\n"
                        text += "In databank                                      0\n"
                elif MockSQXHandler._mode == "rejection":
                    # Stopped (or unknown) in rejection mode — keep the
                    # last generated count visible for the monitor, and
                    # report the stop the way a real SQX daemon does so the
                    # dispatch loop breaks promptly on an early stop (e.g.
                    # an LLM-monitor-initiated stop).
                    text += f"Strategies generated                            {camp.get('generated', 0)}\n"
                    text += "Running time so far                          4 s.\n"
                    text += "In databank                                      0\n"
                    if camp.get("status") == "stopped":
                        text += "Project execution stopped\n"
                else:
                    text += "Strategies generated                              0\n"
                    text += "Running time so far                          0 ms.\n"
                    text += "In databank                                      0\n"
                return self._send_text(text)
            if action == "action=stop":
                with MockSQXHandler._lock:
                    MockSQXHandler._campaigns[name] = {"status": "stopped", "progress": 0}
                return self._send_text(f"Project execution stopped.\n")

        if parts[0] == "-databank":
            action = parts[1] if len(parts) > 1 else ""
            project = ""
            for p in parts[2:]:
                if p.startswith("project="):
                    project = p[8:]
            if action == "action=list":
                if MockSQXHandler._mode == "rejection":
                    return self._send_text(
                        "List of available databanks\n--------------------------------------------------\nResults, Records: 0\nInitial population, Records: 0\nLast generation, Records: 0\n"
                    )
                return self._send_text(
                    f"List of available databanks\n--------------------------------------------------\nResults, Records: 3\nInitial population, Records: 0\nLast generation, Records: 0\n"
                )
            if action == "action=export":
                self._generate_mock_exports(project)
                return self._send_text("Databank contents exported.\n")

        return self._send_text(f"Unrecognized command {cmd}.", status=400)

    def _simulate_campaign(self, name: str):
        """Simulate campaign progress and completion.

        In rejection mode the campaign never completes on its own: the thread
        exits immediately and the campaign stays ``running`` (with a growing
        generated count) until an explicit ``-project action=stop``.
        """
        if MockSQXHandler._mode == "rejection":
            return
        for i in range(1, 5):
            with MockSQXHandler._lock:
                camp = MockSQXHandler._campaigns.get(name)
                if camp:
                    camp["progress"] = i * 25
            import time
            time.sleep(0.5)
        with MockSQXHandler._lock:
            MockSQXHandler._campaigns[name] = {"status": "completed", "progress": 100}

    def _generate_mock_exports(self, project: str) -> Any:
        """Generate mock export files for a completed project."""
        import csv

        base = MockSQXHandler._export_dir / project
        base.mkdir(parents=True, exist_ok=True)

        trades = []
        equity = 10000.0
        for i in range(10):
            pnl = random.uniform(-100, 150)
            equity += pnl
            trades.append({
                "id": i + 1,
                "entry_time": f"2024-01-{(i+1):02d} 00:00:00",
                "exit_time": f"2024-01-{(i+1):02d} 12:00:00",
                "direction": random.choice(["long", "short"]),
                "pnl": round(pnl, 2),
                "equity": round(equity, 2),
            })

        trades_path = base / "trades.csv"
        with trades_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=trades[0].keys())
            writer.writeheader()
            writer.writerows(trades)

        equity_path = base / "equity.csv"
        with equity_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "equity"])
            eq = 10000.0
            for i in range(10):
                eq += random.uniform(-100, 150)
                writer.writerow([f"2024-01-{(i+1):02d} 00:00:00", round(eq, 2)])

        stats = {
            "total_trades": len(trades),
            "net_profit": round(sum(t["pnl"] for t in trades), 2),
            "profit_factor": round(abs(sum(t["pnl"] for t in trades if t["pnl"] > 0)) / max(abs(sum(t["pnl"] for t in trades if t["pnl"] < 0)), 0.01), 2),
            "sharpe_ratio": round(random.uniform(0.5, 1.5), 2),
            "max_drawdown": round(random.uniform(5, 20), 2),
        }
        stats_path = base / "statistics.json"
        stats_path.write_text(json.dumps(stats, indent=2))

        strategies = [
            {
                "Name": "strat_alpha",
                "Profit Factor": round(random.uniform(1.5, 2.5), 2),
                "Sharpe Ratio": round(random.uniform(1.0, 2.0), 2),
                "Win Rate": round(random.uniform(0.45, 0.65), 2),
                "Trades": random.randint(80, 200),
                "Max DD": round(random.uniform(5.0, 15.0), 2),
                "MC p10": round(random.uniform(-500, 500), 2),
                "WF IS Sharpe": round(random.uniform(1.5, 2.5), 2),
                "WF OOS Sharpe": round(random.uniform(1.2, 2.0), 2),
                "WF Cycles": random.choice([0, 12]),
            },
            {
                "Name": "strat_beta",
                "Profit Factor": round(random.uniform(6.0, 8.0), 2),
                "Sharpe Ratio": round(random.uniform(3.0, 4.0), 2),
                "Win Rate": round(random.uniform(0.70, 0.85), 2),
                "Trades": random.randint(3, 8),
                "Max DD": round(random.uniform(2.0, 8.0), 2),
                "MC p10": round(random.uniform(-200, 200), 2),
                "WF IS Sharpe": round(random.uniform(2.0, 3.0), 2),
                "WF OOS Sharpe": round(random.uniform(1.0, 1.5), 2),
                "WF Cycles": random.choice([0, 12]),
            },
            {
                "Name": "strat_gamma",
                "Profit Factor": round(random.uniform(1.2, 2.0), 2),
                "Sharpe Ratio": round(random.uniform(0.8, 1.5), 2),
                "Win Rate": round(random.uniform(0.40, 0.55), 2),
                "Trades": random.randint(50, 150),
                "Max DD": round(random.uniform(8.0, 20.0), 2),
                "MC p10": round(random.uniform(-800, -100), 2),
                "WF IS Sharpe": round(random.uniform(1.0, 1.8), 2),
                "WF OOS Sharpe": round(random.uniform(0.3, 0.6), 2),
                "WF Cycles": 12,
            },
            {
                "Name": "strat_delta",
                "Profit Factor": round(random.uniform(1.3, 2.2), 2),
                "Sharpe Ratio": round(random.uniform(0.9, 1.7), 2),
                "Win Rate": round(random.uniform(0.48, 0.60), 2),
                "Trades": random.randint(60, 180),
                "Max DD": round(random.uniform(6.0, 18.0), 2),
                "MC p10": round(random.uniform(-300, 100), 2),
                "WF IS Sharpe": round(random.uniform(1.4, 2.2), 2),
                "WF OOS Sharpe": round(random.uniform(1.3, 2.1), 2),
                "WF Cycles": 12,
            },
        ]

        strategies_path = base / "strategies.csv"
        with strategies_path.open("w", newline="") as f:
            fieldnames = [
                "Name",
                "Profit Factor",
                "Sharpe Ratio",
                "Win Rate",
                "Trades",
                "Max DD",
                "MC p10",
                "WF IS Sharpe",
                "WF OOS Sharpe",
                "WF Cycles",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for s in strategies:
                writer.writerow(s)

        try:
            return self._send_text(f"Exported {base}\n")
        except Exception:
            pass


class MockSQXServer:
    """Lightweight HTTP server that mocks sqcli behavior for demos.

    ``mode`` selects the simulated campaign behavior:

    - ``normal`` (default): campaigns run the full lifecycle and complete.
    - ``rejection``: zero-acceptance simulation — generated count grows,
      databank record count stays at 0, campaign never completes until
      ``action=stop``.

    The mode is applied to ``MockSQXHandler`` at construction and start time
    so every per-request handler instance observes it.
    """

    _instance: "MockSQXServer | None" = None

    def __init__(
        self,
        host: str = _MOCK_HOST,
        port: int = _MOCK_PORT,
        mode: str = "normal",
    ):
        self.host = host
        self.port = port
        self.mode = mode
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        MockSQXHandler._mode = mode

    @classmethod
    def instance(
        cls,
        host: str = _MOCK_HOST,
        port: int = _MOCK_PORT,
        mode: str = "normal",
    ) -> "MockSQXServer":
        if cls._instance is None:
            cls._instance = cls(host=host, port=port, mode=mode)
        else:
            # Keep the singleton and handler in sync so callers can opt into
            # rejection mode without restarting the server.
            cls._instance.mode = mode
            MockSQXHandler._mode = mode
        return cls._instance

    @classmethod
    def reset(cls):
        inst = cls._instance
        if inst is not None:
            inst.stop()
            cls._instance = None
        MockSQXHandler._mode = "normal"

    def start(self):
        MockSQXHandler._mode = self.mode
        if self._server is not None:
            try:
                import httpx
                httpx.get(f"http://{self.host}:{self.port}/call?cmd=-h", timeout=2)
                return
            except Exception:
                self.stop()

        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
        except OSError:
            pass
        else:
            s.close()
        self._server = HTTPServer((self.host, self.port), MockSQXHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Mock SQX server started on http://%s:%d", self.host, self.port)

    def stop(self):
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            self._server = None
            self._thread = None

    def is_running(self) -> bool:
        return self._server is not None
