"""Everything-style desktop UI. No browser, HTTP server or cloud APIs."""

import json
import ctypes
import logging
import os
import subprocess
import sys
import winreg
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QLockFile, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar,
    QPushButton, QStyle, QSystemTrayIcon, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QComboBox,
)

from .index import canonical
from .worker import Worker


def save_settings(root, settings):
    path = root / "settings" / "settings.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def startup_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            winreg.QueryValueEx(key, "EasyThing")
            return True
    except FileNotFoundError:
        return False


def set_startup(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            entry = Path(sys.argv[0]).resolve()
            command = f'"{sys.executable}" --tray' if entry.suffix.lower() == ".exe" else f'"{sys.executable}" "{entry}" --tray'
            winreg.SetValueEx(key, "EasyThing", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "EasyThing")
            except FileNotFoundError:
                pass


class Window(QMainWindow):
    def __init__(self, root, settings, cpu_only=False):
        super().__init__()
        self.root, self.settings = root, settings
        self.request_id = 0
        self.rows = []
        self.exiting = False
        self.setWindowTitle("EasyThing")
        self.resize(1000, 620)
        container = QWidget()
        layout = QVBoxLayout(container)
        self.setCentralWidget(container)
        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search your files by meaning…")
        self.search_box.setAccessibleName("Search local files")
        self.kind = QComboBox()
        self.kind.addItems(["All", "Documents", "Images"])
        search_row.addWidget(QLabel("Search:"))
        search_row.addWidget(self.search_box, 1)
        search_row.addWidget(self.kind)
        layout.addLayout(search_row)
        buttons = QHBoxLayout()
        add = QPushButton("Add Folder")
        add.clicked.connect(self.add_folder)
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.show_settings)
        self.download_button = QPushButton("Download / Retry model")
        self.download_button.clicked.connect(self.download)
        self.pause = QPushButton("Pause indexing")
        self.pause.setCheckable(True)
        self.pause.toggled.connect(self.toggle_pause)
        for button in (add, settings_button, self.download_button, self.pause):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.folders_label = QLabel()
        layout.addWidget(self.folders_label)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Match", "Location", "Type", "Modified"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.cellDoubleClicked.connect(lambda row, _: self.open_file(row))
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.context_menu)
        layout.addWidget(self.table, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        self.issue_label = QLabel()
        self.issue_label.setWordWrap(True)
        self.issue_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.issue_label)
        self.statusBar().showMessage("Select folders to search. Only folders you add will be indexed.")
        self.worker = Worker(root, settings, cpu_only)
        self.worker.status.connect(self.statusBar().showMessage)
        self.worker.results.connect(self.show_results)
        self.worker.progress.connect(self.index_progress)
        self.worker.issue.connect(self.issue_label.setText)
        self.worker.download_progress.connect(self.model_progress)
        self.worker.model_ready.connect(self.model_ready)
        self.worker.download_finished.connect(self.download_finished)
        self.worker.finished.connect(self.finish_exit)
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(300)
        self.debounce.timeout.connect(self.search)
        self.search_box.textChanged.connect(self.changed_query)
        self.kind.currentTextChanged.connect(self.changed_query)
        self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), self)
        menu = QMenu(self)
        menu.addAction("Open EasyThing", self.show_window)
        self.tray_pause = menu.addAction("Pause indexing")
        self.tray_pause.setCheckable(True)
        self.tray_pause.toggled.connect(self.pause.setChecked)
        menu.addAction("Exit", self.exit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window()
                                    if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()
        self.update_folder_label()
        self.worker.start()

    def show_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.search_box.setFocus()

    def update_folder_label(self):
        enabled = [folder["path"] for folder in self.settings["folders"] if folder["enabled"]]
        self.folders_label.setText("Search folders: " + " · ".join(enabled) if enabled else "Select folders to search → Add Folder")

    def update_folders(self):
        save_settings(self.root, self.settings)
        self.update_folder_label()
        self.worker.submit("folders", [dict(folder) for folder in self.settings["folders"]])
        self.changed_query()

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select a folder to search")
        if path and canonical(path) not in {canonical(item["path"]) for item in self.settings["folders"]}:
            self.settings["folders"].append({"path": str(Path(path).resolve()), "enabled": True, "recursive": True})
            self.update_folders()

    def show_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("EasyThing Settings")
        dialog.resize(750, 350)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select folders to search. Removing a folder deletes only its EasyThing index."))
        folders = QTableWidget(len(self.settings["folders"]), 3)
        folders.setHorizontalHeaderLabels(["Folder", "Enabled", "Include subfolders"])
        folders.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        folders.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for number, folder in enumerate(self.settings["folders"]):
            item = QTableWidgetItem(folder["path"])
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            folders.setItem(number, 0, item)
            for column, key in ((1, "enabled"), (2, "recursive")):
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                check.setCheckState(Qt.CheckState.Checked if folder[key] else Qt.CheckState.Unchecked)
                folders.setItem(number, column, check)
        layout.addWidget(folders)
        remove = QPushButton("Remove selected folder from index")
        remove.clicked.connect(lambda: folders.removeRow(folders.currentRow()) if folders.currentRow() >= 0 else None)
        layout.addWidget(remove)
        startup = QCheckBox("Start EasyThing when I sign in to Windows")
        startup.setChecked(startup_enabled())
        layout.addWidget(startup)
        controls = QHBoxLayout()
        rebuild = QPushButton("Rebuild Index")
        rebuild.clicked.connect(self.rebuild)
        controls.addWidget(rebuild)
        controls.addStretch()
        save = QPushButton("Save")
        save.clicked.connect(dialog.accept)
        controls.addWidget(save)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        controls.addWidget(cancel)
        layout.addLayout(controls)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                set_startup(startup.isChecked())
                self.settings["folders"] = [{
                    "path": folders.item(row, 0).text(),
                    "enabled": folders.item(row, 1).checkState() == Qt.CheckState.Checked,
                    "recursive": folders.item(row, 2).checkState() == Qt.CheckState.Checked,
                } for row in range(folders.rowCount())]
                self.update_folders()
            except Exception:
                logging.exception("Settings could not be saved")
                self.issue_label.setText("Settings could not be saved. Check that your user data folder is writable.")

    def rebuild(self):
        if QMessageBox.question(self, "Rebuild local index", "Rebuild the EasyThing search index?\nOriginal documents and photos will never be deleted.") == QMessageBox.StandardButton.Yes:
            self.worker.submit("rebuild")

    def toggle_pause(self, paused):
        self.pause.setText("Resume indexing" if paused else "Pause indexing")
        self.tray_pause.setChecked(paused)
        self.worker.submit("pause", paused)

    def download(self):
        self.download_button.setEnabled(False)
        self.issue_label.clear()
        self.worker.submit("download")

    def download_finished(self):
        self.download_button.setEnabled(True)
        self.progress_bar.hide()

    def model_progress(self, downloaded, total):
        self.progress_bar.show()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(round(downloaded * 100 / total))
        self.progress_bar.setFormat("Downloading model: %p%")

    def model_ready(self):
        self.progress_bar.hide()
        self.download_button.setEnabled(True)
        self.changed_query()

    def index_progress(self, done, total, name):
        self.progress_bar.setVisible(total > done)
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)
        self.progress_bar.setFormat(f"Indexing {done:,} / {total:,} files")
        if name:
            self.statusBar().showMessage(f"Current: {name}")
        if total and done == total and self.search_box.text().strip():
            self.changed_query()

    def changed_query(self, *_):
        self.request_id += 1
        self.debounce.start()

    def search(self):
        text = self.search_box.text().strip()
        if not text:
            self.show_results(self.request_id, [])
        else:
            self.worker.submit("search", (self.request_id, text, self.kind.currentText()))

    def show_results(self, request_id, rows):
        if request_id != self.request_id:
            return
        self.rows = rows
        self.table.setRowCount(len(rows))
        for number, row in enumerate(rows):
            match = row["match"]
            if row["path"].endswith(".pptx") and not row["visual"]:
                match += " · text only"
            values = [row["name"], match, str(Path(row["path"]).parent),
                      Path(row["path"]).suffix.upper().lstrip("."),
                      datetime.fromtimestamp(row["modified"]).strftime("%Y-%m-%d %H:%M")]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(row["content"][:1000] or row["path"])
                self.table.setItem(number, column, item)
        self.statusBar().showMessage(f"{len(rows)} files")

    def open_file(self, row):
        if 0 <= row < len(self.rows):
            try:
                os.startfile(self.rows[row]["path"])
            except OSError:
                self.issue_label.setText("This file could not be opened. It may have moved or been deleted.")

    def context_menu(self, position):
        row = self.table.rowAt(position.y())
        if not 0 <= row < len(self.rows):
            return
        path = self.rows[row]["path"]
        menu = QMenu(self)
        menu.addAction("Open", lambda: self.open_file(row))
        menu.addAction("Open file location", lambda: subprocess.Popen(["explorer.exe", "/select,", path]))
        menu.addAction("Copy path", lambda: QApplication.clipboard().setText(path))
        menu.exec(self.table.viewport().mapToGlobal(position))

    def closeEvent(self, event):
        if self.exiting:
            event.accept()
        else:
            self.hide()
            event.ignore()

    def exit_app(self):
        self.exiting = True
        self.setEnabled(False)
        self.statusBar().showMessage("Finishing the current file before exiting…")
        self.worker.submit("quit")

    def finish_exit(self):
        if self.exiting:
            self.tray.hide()
            QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("EasyThing")
    app.setQuitOnLastWindowClosed(False)
    root = Path(os.environ["LOCALAPPDATA"]) / "EasyThing"
    for directory in ("models", "index", "cache", "settings", "logs"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(root / "settings" / "running.lock"))
    if not lock.tryLock(0):
        QMessageBox.information(None, "EasyThing", "EasyThing is already running. Open it from the system tray.")
        return 0
    # Inno Setup uses this user-session mutex to protect upgrades/uninstalls.
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, False, "Local\\EasyThingDesktop")
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        root / "logs" / "easything.log", maxBytes=2_000_000, backupCount=2, encoding="utf-8",
    )], format="%(asctime)s %(levelname)s %(message)s")
    settings = {"folders": []}
    file = root / "settings" / "settings.json"
    try:
        if file.exists():
            settings = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(settings.get("folders"), list):
                raise ValueError("Invalid settings")
            for folder in settings["folders"]:
                if not isinstance(folder.get("path"), str) or not folder["path"] or not isinstance(folder.get("enabled"), bool) or not isinstance(folder.get("recursive"), bool):
                    raise ValueError("Invalid folder settings")
    except (ValueError, KeyError, TypeError, OSError):
        logging.exception("Settings could not be read")
        QMessageBox.warning(None, "EasyThing", "Settings could not be read. Please select your folders again. The existing settings file is preserved until you save new settings.")
        settings = {"folders": []}
    window = Window(root, settings, "--cpu" in sys.argv)
    def stop_worker():
        window.worker.submit("quit")
        window.worker.wait()
    app.aboutToQuit.connect(stop_worker)
    if "--tray" not in sys.argv or not settings["folders"]:
        window.show()
    try:
        return app.exec()
    finally:
        if mutex:
            kernel.CloseHandle(mutex)
