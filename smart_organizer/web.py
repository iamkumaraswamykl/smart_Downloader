from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import os

from flask import Flask, jsonify, render_template, request

from .config import APP_NAME, DEFAULT_CATEGORIES, DEFAULT_DB_PATH, DEFAULT_LOG_PATH
from .organizer import OrganizerService


service = OrganizerService(DEFAULT_DB_PATH, DEFAULT_LOG_PATH)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")

    @app.get("/")
    def landing():
        return render_template("landing.html", app_name=APP_NAME)

    @app.get("/dashboard")
    def index():
        return render_template("index.html", app_name=APP_NAME)

    @app.get("/api/status")
    def status():
        return jsonify(_status_payload())

    @app.post("/api/start")
    def start():
        payload = request.get_json(force=True, silent=True) or {}
        watch_path = payload.get("watch_path") or os.getenv("ORGANIZER_WATCH_PATH") or _downloads_path()
        destination_root = payload.get("destination_root") or os.getenv("ORGANIZER_DESTINATION_ROOT") or ""
        try:
            service.start(Path(watch_path), Path(destination_root) if destination_root else None)
            process_existing = bool(payload.get("process_existing", False))
            queued = service.process_existing_files() if process_existing else 0
            data = _status_payload()
            data["queued_existing"] = queued
            return jsonify(data)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/stop")
    def stop():
        service.stop()
        return jsonify(_status_payload())

    @app.post("/api/process")
    def process_now():
        payload = request.get_json(force=True, silent=True) or {}
        path = payload.get("path")
        destination_root = payload.get("destination_root") or ""
        if not path:
            return jsonify({"error": "Missing file path."}), 400
        try:
            action_id = service.process_file_now(Path(path), Path(destination_root) if destination_root else None)
            return jsonify({"id": action_id, "actions": service.db.list_actions(50)})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/actions")
    def actions():
        limit = _bounded_int(request.args.get("limit"), default=100, minimum=1, maximum=500)
        return jsonify(service.db.list_actions(limit))

    @app.get("/api/summary")
    def summary():
        return jsonify(service.db.summary())

    @app.post("/api/actions/<int:action_id>/undo")
    def undo(action_id: int):
        try:
            return jsonify(service.undo(action_id))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/actions/undo_all")
    def undo_all():
        try:
            return jsonify(service.undo_all())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/actions/clear")
    def clear_history():
        try:
            service.clear_history()
            return jsonify({"status": "success"})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/actions/<int:action_id>/reclassify")
    def reclassify(action_id: int):
        payload = request.get_json(force=True, silent=True) or {}
        category = payload.get("category", "")
        try:
            return jsonify(service.reclassify(action_id, category))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/categories")
    def categories():
        return jsonify(
            [
                {
                    "name": name,
                    "folder": cfg.get("folder", name),
                    "description": cfg.get("description", ""),
                }
                for name, cfg in DEFAULT_CATEGORIES.items()
            ]
        )

    @app.get("/api/browse")
    def browse():
        path = request.args.get("path") or ""
        try:
            return jsonify(_browse_path(path))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/logs")
    def logs():
        lines = _bounded_int(request.args.get("lines"), default=120, minimum=1, maximum=1000)
        return jsonify({"lines": _tail(DEFAULT_LOG_PATH, lines)})
    
    @app.post("/api/logs/clear")
    def clear_logs():
        try:
            service.clear_logs()
            return jsonify({"status": "success"})
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    return app


def _status_payload() -> Dict[str, object]:
    status = service.status()
    return {
        "running": status.running,
        "watch_path": status.watch_path,
        "destination_root": status.destination_root,
        "queued": status.queued,
        "default_downloads": _downloads_path(),
        "llm_provider": os.getenv("ORGANIZER_LLM_PROVIDER", "local-semantic") or "local-semantic",
    }


def _downloads_path() -> str:
    home = Path.home()
    downloads = home / "Downloads"
    return str(downloads if downloads.exists() else home)


def _browse_path(raw_path: str) -> Dict[str, object]:
    if raw_path:
        path = Path(raw_path).expanduser().resolve()
    else:
        path = Path(_downloads_path()).resolve()

    if not path.exists() or not path.is_dir():
        raise ValueError(f"Directory not found: {path}")

    directories: List[Dict[str, str]] = []
    for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
        try:
            if child.is_dir() and not child.name.startswith("."):
                directories.append({"name": child.name, "path": str(child.resolve())})
        except OSError:
            continue

    roots = [{"name": "Home", "path": str(Path.home())}, {"name": "Downloads", "path": _downloads_path()}]
    if os.name == "nt":
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:\\")
            if drive.exists():
                roots.append({"name": f"{letter}: drive", "path": str(drive)})
    else:
        roots.append({"name": "Root", "path": "/"})

    parent = str(path.parent) if path.parent != path else ""
    return {"path": str(path), "parent": parent, "directories": directories, "roots": roots}


def _tail(path: Path, lines: int) -> List[str]:
    if not path.exists():
        return []
    lines = max(1, min(lines, 1000))
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()[-lines:]


def _bounded_int(raw_value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw_value)) if raw_value not in {None, ""} else default
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))
