"""One worker thread for indexing and inference; watchdog only queues paths."""

import gc
import logging
import queue
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .index import Index, canonical, in_scope, selected_files
from .model import Embedder, MODEL_FILE, download_model
from .readers import SUPPORTED


class FileEvents(FileSystemEventHandler):
    def __init__(self, commands):
        self.commands = commands

    def on_any_event(self, event):
        if event.event_type not in {"created", "modified", "deleted", "moved"}:
            return
        if event.is_directory and event.event_type == "modified":
            return
        if event.is_directory:
            self.commands.put(("reconcile", None))
        else:
            self.commands.put(("event", str(event.src_path)))
            if getattr(event, "dest_path", None):
                self.commands.put(("event", str(event.dest_path)))


class Worker(QThread):
    status = Signal(str)
    results = Signal(int, object)
    progress = Signal(int, int, str)
    download_progress = Signal(int, int)
    issue = Signal(str)
    model_ready = Signal()
    download_finished = Signal()

    def __init__(self, root, settings, cpu_only=False):
        super().__init__()
        self.root = Path(root)
        self.folders = [dict(folder) for folder in settings.get("folders", [])]
        self.cpu_only = cpu_only
        self.commands = queue.Queue()
        self.pending = {}
        self.observer = None
        self.index = None
        self.paused = False
        self.stopping = False
        self.done = self.total = 0
        self.reconcile_at = None
        self.latest_search = 0

    def submit(self, command, value=None):
        if command == "search":
            self.latest_search = value[0]
        self.commands.put((command, value))

    def stop_watch(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def watch(self):
        self.stop_watch()
        observer = Observer()
        for folder in self.folders:
            if folder["enabled"] and Path(folder["path"]).is_dir():
                observer.schedule(FileEvents(self.commands), folder["path"], recursive=folder["recursive"])
        observer.start()
        self.observer = observer

    def reconcile(self):
        if self.index is None:
            return
        signatures = self.index.signatures()
        removed = [path for path in signatures if not in_scope(path, self.folders, enabled_only=False)
                   or (in_scope(path, self.folders) and not Path(path).exists())]
        self.index.remove_many(removed)
        # Disabled folders keep their index but are never scanned or searched.
        for path in selected_files(self.folders):
            try:
                stat = Path(path).stat()
                if signatures.get(path) != (stat.st_size, stat.st_mtime_ns):
                    self.pending.setdefault(path, (0, 0, False))
            except OSError:
                logging.exception("Could not inspect file: %s", path)
                self.issue.emit(f"Could not read {Path(path).name}; other files will continue.")
        self.done, self.total = 0, len(self.pending)
        self.progress.emit(self.done, self.total, "")
        self.status.emit("Ready" if not self.pending else (
            "Indexing changed files" if (self.root / "models" / MODEL_FILE).is_file()
            else "Download EmbeddingGemma 2 to start indexing"
        ))

    def run(self):
        self.embedder = Embedder(self.root, cpu_only=self.cpu_only)
        try:
            try:
                self.index = Index(self.root, self.embedder)
                self.watch()
                self.reconcile()
            except Exception:
                logging.exception("Index initialization failed")
                self.issue.emit("The local index could not be opened. Use Settings → Rebuild Index.")
            while not self.stopping:
                try:
                    command, value = self.commands.get(timeout=0.05)
                except queue.Empty:
                    command, value = None, None
                try:
                    if command == "quit":
                        self.stopping = True
                        continue
                    if command == "pause":
                        self.paused = value
                        self.status.emit("Indexing paused" if value else "Indexing resumed")
                    elif command == "folders":
                        self.folders = value
                        self.pending.clear()
                        self.watch()
                        self.reconcile()
                    elif command == "reconcile":
                        self.reconcile_at = time.monotonic() + 1
                    elif command == "event":
                        path = canonical(value)
                        if Path(path).suffix.lower() in SUPPORTED and in_scope(path, self.folders):
                            self.pending[path] = (time.monotonic() + 1, 0, True)
                            self.total = self.done + len(self.pending)
                    elif command == "download":
                        self.status.emit("Downloading EmbeddingGemma 2…")
                        try:
                            download_model(self.root / "models", self.download_progress.emit)
                            self.reconcile()
                            self.model_ready.emit()
                            self.status.emit("Model ready")
                        except Exception:
                            logging.exception("Model download failed")
                            self.issue.emit("Model download failed. Check your connection and click Download / Retry.")
                        finally:
                            self.download_finished.emit()
                    elif command == "search":
                        request_id, text, kind = value
                        if request_id != self.latest_search:
                            continue
                        if self.index is None:
                            raise ValueError("Rebuild the local index before searching.")
                        self.results.emit(request_id, self.index.search(text, self.folders, kind))
                    elif command == "rebuild":
                        self.stop_watch()
                        if self.index:
                            self.index.close()
                        self.index = None
                        gc.collect()
                        target = (self.root / "index").resolve()
                        if target.parent != self.root.resolve() or target.name != "index":
                            raise ValueError("Invalid local index path.")
                        # Preserve the old local database for recovery; never delete source files.
                        if target.exists():
                            target.rename(self.root / "cache" / f"index-backup-{time.time_ns()}")
                        self.index = Index(self.root, self.embedder)
                        self.watch()
                        self.reconcile()
                        self.status.emit("Local index rebuilt; reindexing selected folders")
                    if self.reconcile_at and time.monotonic() >= self.reconcile_at:
                        self.reconcile_at = None
                        self.reconcile()
                    if command is not None:
                        continue  # Search and control commands have priority over indexing.
                    if self.index is None or self.paused or not self.pending:
                        continue
                    if not (self.root / "models" / MODEL_FILE).is_file():
                        continue
                    path = next((p for p, (when, _, _) in self.pending.items() if when <= time.monotonic()), None)
                    if path is None:
                        continue
                    _, attempts, force = self.pending.pop(path)
                    if not in_scope(path, self.folders):
                        continue
                    self.progress.emit(self.done, self.total, Path(path).name)
                    try:
                        if Path(path).exists():
                            note = self.index.index_file(path, force=force)
                            if note not in {"indexed", "unchanged"}:
                                self.issue.emit(f"{Path(path).name}: {note}")
                        else:
                            self.index.remove(path)
                    except Exception:
                        logging.exception("File indexing failed: %s", path)
                        if attempts < 2:
                            self.pending[path] = (time.monotonic() + 2, attempts + 1, force)
                            continue
                        self.issue.emit(f"Could not index {Path(path).name}. Other files will continue; details are in logs.")
                    self.done += 1
                    self.progress.emit(self.done, self.total, "")
                    if not self.pending:
                        self.status.emit(f"Ready · {self.embedder.backend}")
                except Exception as error:
                    logging.exception("Worker command failed: %s", command)
                    self.issue.emit(str(error) if isinstance(error, ValueError) else
                                    "The operation failed. Check logs, or use Rebuild Index if search keeps failing.")
        finally:
            self.stop_watch()
            if self.index:
                self.index.close()
            self.embedder.close()
