from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty
from typing import Dict, Optional
import hashlib
import logging
import shutil
import threading
import time

from .classifier import ClassificationResult, SemanticClassifier
from .config import DEFAULT_CATEGORIES, DEFAULT_DB_PATH, DEFAULT_LOG_PATH, TEMP_EXTENSIONS
from .database import OrganizerDatabase
from .extractor import ExtractedContent, extract_text


@dataclass
class ServiceStatus:
    running: bool
    watch_path: str
    destination_root: str
    queued: int


class OrganizerService:
    def __init__(
        self,
        db_path: Path = DEFAULT_DB_PATH,
        log_path: Path = DEFAULT_LOG_PATH,
        stability_seconds: float = 2.0,
        stability_timeout: float = 90.0,
    ):
        self.db = OrganizerDatabase(Path(db_path))
        self.classifier = SemanticClassifier()
        self.stability_seconds = stability_seconds
        self.stability_timeout = stability_timeout
        self.watch_path: Optional[Path] = None
        self.destination_root: Optional[Path] = None
        self.observer = None
        self._queue: Queue[Path] = Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._seen_recently: Dict[str, float] = {}
        self.logger = _build_logger(Path(log_path))

    def start(self, watch_path: Path, destination_root: Optional[Path] = None) -> None:
        try:
            from watchdog.events import FileSystemEventHandler  # type: ignore
            from watchdog.observers import Observer  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "watchdog is not installed. Run `pip install -r requirements.txt` first."
            ) from exc

        watch_path = Path(watch_path).expanduser().resolve()
        if not watch_path.exists() or not watch_path.is_dir():
            raise ValueError(f"Watch path does not exist or is not a directory: {watch_path}")

        if self.is_running:
            self.stop()

        self.watch_path = watch_path
        self.destination_root = (
            Path(destination_root).expanduser().resolve()
            if destination_root
            else (watch_path / "Organized").resolve()
        )
        self.destination_root.mkdir(parents=True, exist_ok=True)

        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

        service = self

        class DownloadEventHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    service.enqueue(Path(event.src_path))

            def on_moved(self, event):
                if not event.is_directory:
                    service.enqueue(Path(event.dest_path))

            def on_modified(self, event):
                if not event.is_directory:
                    service.enqueue(Path(event.src_path))

        self.observer = Observer()
        self.observer.schedule(DownloadEventHandler(), str(watch_path), recursive=False)
        self.observer.start()
        self.logger.info("Started watching %s -> %s", watch_path, self.destination_root)

    def stop(self) -> None:
        self._stop_event.set()
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5)
        self.logger.info("Stopped organizer service")

    @property
    def is_running(self) -> bool:
        return bool(self.observer and self.observer.is_alive())

    def status(self) -> ServiceStatus:
        return ServiceStatus(
            running=self.is_running,
            watch_path=str(self.watch_path or ""),
            destination_root=str(self.destination_root or ""),
            queued=self._queue.qsize(),
        )

    def enqueue(self, path: Path) -> None:
        path = Path(path)
        if self._should_skip(path):
            return

        key = str(path.resolve() if path.exists() else path)
        now = time.time()
        last = self._seen_recently.get(key, 0)
        if now - last < 1.0:
            return
        self._seen_recently[key] = now
        self._queue.put(path)

    def process_existing_files(self) -> int:
        if not self.watch_path:
            raise RuntimeError("Service has no watch path yet.")
        count = 0
        for path in self.watch_path.iterdir():
            if path.is_file() and not self._should_skip(path):
                self.enqueue(path)
                count += 1
        return count

    def process_file_now(self, path: Path, destination_root: Optional[Path] = None) -> int:
        if destination_root:
            self.destination_root = Path(destination_root).expanduser().resolve()
        elif not self.destination_root:
            self.destination_root = Path(path).expanduser().resolve().parent / "Organized"
        self.destination_root.mkdir(parents=True, exist_ok=True)
        return self._process_file(Path(path).expanduser().resolve())

    def undo(self, action_id: int) -> Dict[str, object]:
        action = self.db.get_action(action_id)
        if not action:
            raise ValueError(f"Unknown action id: {action_id}")
        if action["status"] not in {"moved", "reclassified"}:
            raise ValueError(f"Action {action_id} cannot be undone from status {action['status']}.")

        current = Path(action["current_path"])
        original = Path(action["original_path"])
        if not current.exists():
            raise FileNotFoundError(f"Moved file no longer exists: {current}")

        original.parent.mkdir(parents=True, exist_ok=True)
        target = _unique_path(original)
        shutil.move(str(current), str(target))
        self.db.mark_undone(action_id, str(target))
        self.logger.info("Undo action %s: %s -> %s", action_id, current, target)
        return {"id": action_id, "current_path": str(target), "status": "undone"}

    def reclassify(self, action_id: int, category: str) -> Dict[str, object]:
        if category not in DEFAULT_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        action = self.db.get_action(action_id)
        if not action:
            raise ValueError(f"Unknown action id: {action_id}")
        if not self.destination_root:
            current_path = Path(action["current_path"] or action["original_path"])
            self.destination_root = current_path.parent.parent

        current = Path(action["current_path"] or action["original_path"])
        if not current.exists():
            raise FileNotFoundError(f"File does not exist: {current}")

        destination = self._destination_for(current.name, category)
        shutil.move(str(current), str(destination))
        self.db.mark_reclassified(action_id, category, str(destination), str(destination))
        
        # Priority 4: Category Learning
        # Store the corrected pattern for future auto-classification
        if action.get("extracted_preview"):
            self.db.record_learned_pattern(action["extracted_preview"], category)
            
        self.logger.info("Manual reclassify action %s: %s -> %s", action_id, current, destination)
        return {"id": action_id, "category": category, "current_path": str(destination)}

    def undo_all(self) -> Dict[str, object]:
        actions = self.db.get_undoable_actions()
        count = 0
        errors = []
        for action in actions:
            try:
                self.undo(action["id"])
                count += 1
            except Exception as exc:
                errors.append(f"Action {action['id']}: {exc}")
        
        return {"undone_count": count, "errors": errors}

    def clear_history(self) -> None:
        self.db.clear_history()
        self.logger.info("History cleared by user.")

    def clear_logs(self) -> None:
        # Find the log file path from handlers
        log_path = None
        for handler in self.logger.handlers:
            if isinstance(handler, logging.FileHandler):
                log_path = Path(handler.baseFilename)
                break
        
        if log_path and log_path.exists():
            with log_path.open("w", encoding="utf-8") as f:
                f.write("") # Clear the file
            self.logger.info("Logs cleared by user.")

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                path = self._queue.get(timeout=0.5)
            except Empty:
                continue
            try:
                self._process_file(path)
            except Exception as exc:
                self.logger.exception("Failed to process %s", path)
                self.db.record_error(str(path), path.name, str(exc))
            finally:
                self._queue.task_done()

    def _process_file(self, path: Path) -> int:
        path = Path(path).expanduser().resolve()
        if self._should_skip(path):
            raise ValueError(f"Skipped file: {path}")
        if not self._wait_until_stable(path):
            raise TimeoutError(f"File did not become stable in time: {path}")

        extracted = extract_text(path)
        learned = self.db.list_learned_patterns()
        result = self.classifier.classify(extracted.text, path, extracted.mime_type, learned_patterns=learned)
        if extracted.error and result.category == "Uncategorized":
            result = ClassificationResult(
                "Uncategorized",
                result.confidence,
                result.method,
                extracted.error,
                result.matched_terms,
            )

        file_hash = _calculate_hash(path)
        duplicate = self.db.find_duplicate(file_hash)

        if duplicate:
            # Handle duplicate
            dest_folder = self.destination_root / "Duplicates"
            dest_folder.mkdir(parents=True, exist_ok=True)
            destination = _unique_path(dest_folder / path.name)
            shutil.move(str(path), str(destination))
            
            payload = {
                "original_path": str(path),
                "current_path": str(destination),
                "destination_path": str(destination),
                "file_name": path.name,
                "category": "Duplicate",
                "confidence": 1.0,
                "method": "hash_match",
                "mime_type": extracted.mime_type,
                "extractor": extracted.extractor,
                "status": "duplicate",
                "error": f"Duplicate of: {duplicate['file_name']} (Action ID: {duplicate['id']})",
                "extracted_preview": _preview(extracted, result),
                "file_hash": file_hash,
                "moved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
            action_id = self.db.record_action(payload)
            self.logger.info("Detected duplicate: %s (Duplicate of Action ID %s)", path, duplicate["id"])
            return action_id

        destination = self._destination_for(path.name, result.category)
        shutil.move(str(path), str(destination))

        payload = {
            "original_path": str(path),
            "current_path": str(destination),
            "destination_path": str(destination),
            "file_name": path.name,
            "category": result.category,
            "confidence": result.confidence,
            "method": result.method,
            "mime_type": extracted.mime_type,
            "extractor": extracted.extractor,
            "status": "moved",
            "error": extracted.error,
            "extracted_preview": _preview(extracted, result),
            "file_hash": file_hash,
            "moved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        action_id = self.db.record_action(payload)
        self.logger.info(
            "Moved %s -> %s category=%s confidence=%.3f method=%s",
            path,
            destination,
            result.category,
            result.confidence,
            result.method,
        )
        return action_id

    def _destination_for(self, file_name: str, category: str) -> Path:
        destination_root = self.destination_root
        if not destination_root:
            raise RuntimeError("Destination root is not configured.")
        category_cfg = DEFAULT_CATEGORIES.get(category, DEFAULT_CATEGORIES["Uncategorized"])
        folder = destination_root / str(category_cfg.get("folder", "Uncategorized"))
        folder.mkdir(parents=True, exist_ok=True)
        return _unique_path(folder / file_name)

    def _should_skip(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        if suffix in TEMP_EXTENSIONS:
            return True
        if path.name.startswith("."):
            return True
        try:
            resolved = path.resolve()
            if self.destination_root and _is_relative_to(resolved, self.destination_root):
                return True
        except Exception:
            return False
        return False

    def _wait_until_stable(self, path: Path) -> bool:
        deadline = time.time() + self.stability_timeout
        stable_since: Optional[float] = None
        last_size = -1

        while time.time() < deadline:
            if not path.exists() or not path.is_file():
                time.sleep(0.5)
                continue
            try:
                size = path.stat().st_size
                with path.open("rb"):
                    pass
            except OSError:
                stable_since = None
                time.sleep(0.5)
                continue

            if size == last_size:
                stable_since = stable_since or time.time()
                if time.time() - stable_since >= self.stability_seconds:
                    return True
            else:
                last_size = size
                stable_since = None
            time.sleep(0.5)
        return False


def _build_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("smart_organizer")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def _unique_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(1, 10000):
        candidate = path.with_name(f"{stem} ({index}){suffix}")
        if not candidate.exists():
            return candidate
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return path.with_name(f"{stem} ({timestamp}){suffix}")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _preview(extracted: ExtractedContent, result: ClassificationResult) -> str:
    text = extracted.text.strip().replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    if text:
        return text[:420]
    if result.rationale:
        return result.rationale[:420]
    return extracted.error[:420]


def _calculate_hash(path: Path, block_size: int = 65536) -> str:
    sha256 = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            sha256.update(block)
    return sha256.hexdigest()

