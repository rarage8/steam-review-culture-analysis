from __future__ import annotations

import json
import logging
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent.parent
WEB_DIR = ROOT / "web"
STATE_PATH = ROOT / "data" / "refresh_state.json"
COOLDOWN = timedelta(minutes=5)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

refresh_lock = threading.Lock()


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {"cooldown_until": None, "running": False}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"cooldown_until": None, "running": False}


def write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/refresh-status"):
            self._send_json(read_state())
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/api/refresh"):
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        with refresh_lock:
            state = read_state()
            now = datetime.now(timezone.utc)
            cooldown_until = state.get("cooldown_until")
            cooldown_dt = datetime.fromisoformat(cooldown_until) if cooldown_until else None

            if state.get("running"):
                self._send_json({**state, "message": "refresh already running"}, status=409)
                return
            if cooldown_dt and cooldown_dt > now:
                self._send_json({**state, "message": "cooldown active"}, status=429)
                return

            next_state = {
                "running": True,
                "cooldown_until": (now + COOLDOWN).isoformat(),
                "last_started_at": now.isoformat(),
            }
            write_state(next_state)

        try:
            subprocess.run(
                ["python", str(ROOT / "src" / "refresh_dashboard_data.py"), "--detect-new", "--auto-add"],
                cwd=str(ROOT),
                check=True,
            )
            finished_at = datetime.now(timezone.utc).isoformat()
            next_state.update({"running": False, "last_finished_at": finished_at})
            write_state(next_state)
            self._send_json(next_state)
        except subprocess.CalledProcessError as exc:
            failed_state = {
                **next_state,
                "running": False,
                "last_error": str(exc),
            }
            write_state(failed_state)
            self._send_json(failed_state, status=500)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), DashboardHandler)
    logger.info("Serving dashboard on http://127.0.0.1:8000")
    server.serve_forever()
