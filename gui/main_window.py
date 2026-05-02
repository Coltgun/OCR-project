"""
MainWindow — the primary application window for the Simplified Chinese OCR app.

Responsibilities:
  - Host the session status panel, capture controls, and pipeline controls.
  - Wire StateMachine ↔ HotkeyListener ↔ CaptureSession ↔ Pipeline ↔ EpubFormatter.
  - React to StateMachine.state_changed to update UI state (buttons, status bar).
  - Dispatch capture (F9), new section (F10), OCR run (F11), region select (F8).
  - Show the SessionDialog on first run and on "New Session".
  - Save the captured EPUB to disk and report success/failure.

GUI thread safety: all OCR work and EPUB writing happen in QRunnable workers;
results are delivered back to the main thread via Qt signals (queued connections).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, Slot
from PySide6.QtGui import QAction, QCloseEvent, QColor, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from capture.hotkeys import HotkeyListener
from capture.screen_capture import CaptureRegion, ScreenCapture
from capture.session import CaptureSession
from capture.state import AppState, StateMachine
from core.types import Chapter, OCRResult
from gui.about_dialog import AboutDialog
from gui.overlay import CaptureOverlay, RegionBorderOverlay
from gui.qt_log_handler import QtLogHandler
from gui.session_dialog import SessionDialog
from gui.settings_dialog import SettingsDialog
from ocr.pipeline import Pipeline
from ocr.worker import OCRWorker
from output.epub_formatter import EpubFormatter
from output.markdown_formatter import MarkdownFormatter
from output.plain_text_formatter import PlainTextFormatter
from utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window.

    Args:
        config_manager: Initialised ConfigManager instance.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        super().__init__()
        self._config = config_manager
        self._cfg: dict = config_manager._data  # live config dict

        self._session: CaptureSession | None = None
        self._capture_region: CaptureRegion | None = None
        self._ocr_results: list[OCRResult] = []

        self._state_machine = StateMachine(self)
        self._hotkeys = HotkeyListener(self._cfg, self)
        self._screen_capture = ScreenCapture()
        self._border_overlay = RegionBorderOverlay()
        self._capture_overlay: CaptureOverlay | None = None

        self.setWindowTitle("Simplified Chinese OCR")
        self.setMinimumSize(560, 480)

        self._build_menu()
        self._build_central_widget()
        self._build_status_bar()
        self._connect_signals()
        self._install_log_handler()

        self._hotkeys.start()
        self._update_ui_for_state(AppState.IDLE)
        self._update_recent_menu()
        self._update_pipeline_mode_label()
        dark = bool(self._cfg.get("dark_mode", False))
        self._dark_mode_action.setChecked(dark)
        self._apply_theme(dark)
        self._apply_preview_font_size(int(self._cfg.get("preview_font_size", 11)))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        new_session_action = QAction("&New Session…", self)
        new_session_action.setShortcut(QKeySequence("Ctrl+N"))
        new_session_action.triggered.connect(self._start_new_session)
        file_menu.addAction(new_session_action)

        self._recent_menu = file_menu.addMenu("Recent Sessions")

        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(QApplication.quit)
        file_menu.addAction(quit_action)

        view_menu = menu_bar.addMenu("&View")
        self._toggle_border_action = QAction("Toggle Region Border (F7)", self)
        self._toggle_border_action.triggered.connect(self._toggle_border_overlay)
        view_menu.addAction(self._toggle_border_action)

        self._toggle_log_action = QAction("Show Log Panel", self)
        self._toggle_log_action.setCheckable(True)
        self._toggle_log_action.setChecked(False)
        self._toggle_log_action.triggered.connect(self._toggle_log_panel)
        view_menu.addAction(self._toggle_log_action)

        self._dark_mode_action = QAction("Dark Mode", self)
        self._dark_mode_action.setCheckable(True)
        self._dark_mode_action.triggered.connect(self._toggle_dark_mode)
        view_menu.addAction(self._dark_mode_action)

        tools_menu = menu_bar.addMenu("&Tools")
        settings_action = QAction("&Settings…", self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)

        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("&About…", self)
        about_action.triggered.connect(self._open_about)
        help_menu.addAction(about_action)

    def _build_central_widget(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(12)
        root_layout.setContentsMargins(16, 16, 16, 16)

        # Session info row
        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("<b>Session:</b>"))
        self._session_label = QLabel("No session active")
        session_row.addWidget(self._session_label, stretch=1)
        new_btn = QPushButton("New Session…")
        new_btn.clicked.connect(self._start_new_session)
        session_row.addWidget(new_btn)
        root_layout.addLayout(session_row)

        # Region row
        region_row = QHBoxLayout()
        region_row.addWidget(QLabel("<b>Capture region:</b>"))
        self._region_label = QLabel("Not set")
        region_row.addWidget(self._region_label, stretch=1)
        select_btn = QPushButton("Select Region (F8)")
        select_btn.clicked.connect(self._trigger_select_region)
        region_row.addWidget(select_btn)
        root_layout.addLayout(region_row)

        # Section row
        section_row = QHBoxLayout()
        section_row.addWidget(QLabel("<b>Current section:</b>"))
        self._section_label = QLabel("—")
        section_row.addWidget(self._section_label, stretch=1)
        self._new_section_btn = QPushButton("New Section (F10)")
        self._new_section_btn.clicked.connect(self._trigger_new_section)
        section_row.addWidget(self._new_section_btn)
        root_layout.addLayout(section_row)

        # Session notes
        notes_header = QHBoxLayout()
        notes_header.addWidget(QLabel("<b>Session notes:</b>"))
        root_layout.addLayout(notes_header)
        self._notes_edit = QTextEdit()
        self._notes_edit.setMaximumHeight(80)
        self._notes_edit.setPlaceholderText("Optional notes for this session…")
        self._notes_edit.setEnabled(False)
        self._notes_edit.textChanged.connect(self._on_notes_changed)
        root_layout.addWidget(self._notes_edit)

        # Image count row
        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("<b>Images captured:</b>"))
        self._count_label = QLabel("0")
        count_row.addWidget(self._count_label, stretch=1)
        self._capture_btn = QPushButton("Capture (F9)")
        self._capture_btn.clicked.connect(self._trigger_capture)
        count_row.addWidget(self._capture_btn)
        self._reset_count_btn = QPushButton("Reset Count")
        self._reset_count_btn.setEnabled(False)
        self._reset_count_btn.clicked.connect(self._reset_capture_count)
        count_row.addWidget(self._reset_count_btn)
        root_layout.addLayout(count_row)

        root_layout.addStretch()

        # OCR / Export row
        action_row = QHBoxLayout()
        self._ocr_btn = QPushButton("Run OCR (F11)")
        self._ocr_btn.clicked.connect(self._trigger_run_ocr)
        action_row.addWidget(self._ocr_btn)

        self._export_fmt_combo = QComboBox()
        self._export_fmt_combo.addItem("EPUB", userData="epub")
        self._export_fmt_combo.addItem("Plain Text", userData="txt")
        self._export_fmt_combo.addItem("Markdown", userData="md")
        action_row.addWidget(self._export_fmt_combo)

        self._export_btn = QPushButton("Export…")
        self._export_btn.clicked.connect(self._trigger_export)
        self._export_btn.setEnabled(False)
        action_row.addWidget(self._export_btn)
        root_layout.addLayout(action_row)

        # Results preview pane
        preview_header = QHBoxLayout()
        self._preview_label = QLabel("<b>OCR Results:</b> —")
        preview_header.addWidget(self._preview_label, stretch=1)
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_results_to_clipboard)
        preview_header.addWidget(self._copy_btn)
        root_layout.addLayout(preview_header)

        self._preview_pane = QTextEdit()
        self._preview_pane.setReadOnly(True)
        self._preview_pane.setMinimumHeight(80)
        self._preview_pane.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_pane.setPlaceholderText("OCR results will appear here after running OCR…")
        root_layout.addWidget(self._preview_pane)

        # Log panel (collapsed by default)
        self._log_panel = QTextEdit()
        self._log_panel.setReadOnly(True)
        self._log_panel.setMinimumHeight(60)
        self._log_panel.setMaximumHeight(200)
        self._log_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding
        )
        self._log_panel.setVisible(False)
        self._log_panel.setPlaceholderText("OCR log output will appear here…")
        font = self._log_panel.font()
        font.setFamily("Courier New")
        font.setPointSize(9)
        self._log_panel.setFont(font)
        root_layout.addWidget(self._log_panel)

    def _build_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)

        self._open_folder_btn = QPushButton("Open folder")
        self._open_folder_btn.setVisible(False)
        self._open_folder_btn.clicked.connect(self._on_open_export_folder)
        self._status_bar.addPermanentWidget(self._open_folder_btn)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)
        self._status_bar.addPermanentWidget(self._progress_bar)

        self._state_dot = QLabel()
        self._state_dot.setFixedSize(12, 12)
        self._state_dot.setToolTip("Application state")
        self._status_bar.addPermanentWidget(self._state_dot)

        self._state_label = QLabel("IDLE")
        self._status_bar.addPermanentWidget(self._state_label)

        self._pipeline_mode_label = QLabel()
        self._pipeline_mode_label.setToolTip("Active pipeline mode")
        self._status_bar.addPermanentWidget(self._pipeline_mode_label)

        self._status_bar.showMessage("Ready. Start a new session to begin.")

        self._last_export_path: str = ""

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._state_machine.state_changed.connect(self._on_state_changed)

        self._hotkeys.capture_pressed.connect(self._trigger_capture)
        self._hotkeys.new_section_pressed.connect(self._trigger_new_section)
        self._hotkeys.send_to_ocr_pressed.connect(self._trigger_run_ocr)
        self._hotkeys.reset_area_pressed.connect(self._trigger_select_region)
        self._hotkeys.toggle_overlay_pressed.connect(self._toggle_border_overlay)
        self._hotkeys.cancel_pressed.connect(self._trigger_cancel)

    # ------------------------------------------------------------------
    # State machine reactions
    # ------------------------------------------------------------------

    @Slot(object, object)
    def _on_state_changed(self, old: AppState, new: AppState) -> None:
        logger.debug("MainWindow: state %s → %s", old.name, new.name)
        self._update_ui_for_state(new)

    # Stylesheet templates for the state indicator dot.
    _DOT_IDLE = "border-radius:6px; background:#4CAF50;"
    _DOT_BUSY = "border-radius:6px; background:#FFC107;"
    _DOT_ERROR = "border-radius:6px; background:#F44336;"
    _DOT_COLOURS = {
        AppState.IDLE: _DOT_IDLE,
        AppState.SELECTING: _DOT_BUSY,
        AppState.CAPTURING: _DOT_BUSY,
        AppState.OCR_RUNNING: _DOT_BUSY,
        AppState.EXPORTING: _DOT_BUSY,
    }

    def _update_ui_for_state(self, state: AppState) -> None:
        """Enable/disable controls to match the current state."""
        self._state_label.setText(state.name)
        self._state_dot.setStyleSheet(
            self._DOT_COLOURS.get(state, self._DOT_BUSY)
        )
        if state != AppState.IDLE or not self._last_export_path:
            self._open_folder_btn.setVisible(False)
        is_idle = state == AppState.IDLE
        has_session = self._session is not None
        has_region = self._capture_region is not None
        has_results = bool(self._ocr_results)

        self._capture_btn.setEnabled(
            is_idle and has_session and has_region
        )
        self._reset_count_btn.setEnabled(is_idle and has_session)
        self._new_section_btn.setEnabled(is_idle and has_session)
        self._ocr_btn.setEnabled(
            is_idle and has_session
            and self._session is not None
            and self._session.total_images() > 0
        )
        self._export_btn.setEnabled(is_idle and has_results)

        state_messages = {
            AppState.IDLE: "Ready.",
            AppState.SELECTING: "Draw a capture region…  (Esc to cancel)",
            AppState.CAPTURING: "Capturing screenshot…",
            AppState.OCR_RUNNING: "Running OCR pipeline…",
            AppState.EXPORTING: "Exporting EPUB…",
        }
        self._status_bar.showMessage(state_messages.get(state, ""))

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    @Slot()
    def _start_new_session(self) -> None:
        if not self._state_machine.is_idle:
            return
        dlg = SessionDialog(self._config, self)
        if dlg.exec() != SessionDialog.DialogCode.Accepted:
            return

        self._session = CaptureSession(dlg.session_root, resume=dlg.resume)
        self._ocr_results = []
        self._clear_preview()
        self._load_notes()
        self._record_recent_session(str(dlg.session_root))
        self._update_session_labels()
        self._export_btn.setEnabled(False)
        logger.info(
            "MainWindow: session started at '%s' (resume=%s).",
            dlg.session_root, dlg.resume,
        )
        self._status_bar.showMessage(
            f"Session active: {dlg.session_root}  |  "
            f"Section {self._session.current_folder}"
        )
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _trigger_select_region(self) -> None:
        if not self._state_machine.select_region():
            return
        self._border_overlay.hide()
        self._capture_overlay = CaptureOverlay()
        self._capture_overlay.region_selected.connect(self._on_region_selected)
        self._capture_overlay.cancelled.connect(self._on_region_cancelled)
        self._capture_overlay.show_fullscreen()

    @Slot()
    def _on_region_selected(self, rect) -> None:
        self._capture_region = CaptureRegion(
            x=rect.x(), y=rect.y(),
            width=rect.width(), height=rect.height(),
        )
        self._region_label.setText(
            f"({rect.x()}, {rect.y()})  {rect.width()}×{rect.height()}"
        )
        self._border_overlay.update_region_from_qrect(rect)
        self._border_overlay.show()
        self._state_machine.selection_done()
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _on_region_cancelled(self) -> None:
        self._state_machine.cancel()
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _trigger_capture(self) -> None:
        if self._session is None or self._capture_region is None:
            return
        if not self._state_machine.capture():
            return

        import cv2  # noqa: PLC0415 — deferred to avoid DLL issues at import time
        rotation = self._cfg.get("rotation_mode", "none")
        try:
            image = self._screen_capture.grab_and_rotate(
                self._capture_region, rotation
            )
            save_path = self._session.get_next_image_path()
            cv2.imwrite(str(save_path), image)
            logger.info("MainWindow: captured → %s", save_path)
            self._update_count_label()
            self._state_machine.capture_done()
        except Exception as exc:
            logger.error("MainWindow: capture failed: %s", exc)
            self._status_bar.showMessage(f"Capture error: {exc}")
            self._state_machine.capture_error()
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _trigger_new_section(self) -> None:
        if self._session is None or not self._state_machine.is_idle:
            return
        folder = self._session.new_section()
        self._section_label.setText(str(folder))
        self._status_bar.showMessage(f"New section: folder {folder}")
        self._clear_preview()

    @Slot()
    def _trigger_run_ocr(self) -> None:
        if self._session is None:
            return
        if not self._state_machine.run_ocr():
            return

        image_paths: list[Path] = []
        for fn in sorted(
            range(1, self._session.current_folder + 1), key=lambda x: x
        ):
            folder = self._session.folder_path(fn)
            pngs = sorted(
                [p for p in folder.iterdir() if p.suffix.lower() == ".png"],
                key=lambda p: int(p.stem),
            )
            image_paths.extend(pngs)

        if not image_paths:
            self._status_bar.showMessage("No images to process.")
            self._state_machine.ocr_done()
            return

        worker = OCRWorker(self._cfg, image_paths, self)
        worker.signals.results_ready.connect(self._on_ocr_results)
        worker.signals.error_occurred.connect(self._on_ocr_error)
        worker.signals.progress.connect(self._on_ocr_progress)
        QThreadPool.globalInstance().start(worker)
        self._status_bar.showMessage(
            f"OCR running on {len(image_paths)} image(s)…"
        )

    @Slot(list)
    def _on_ocr_results(self, results: list[OCRResult]) -> None:
        raw_count = len(results)
        min_conf = float(self._cfg.get("ocr_min_confidence", 0.0))
        if min_conf > 0.0:
            results = [r for r in results if r.confidence >= min_conf]
        kept_count = len(results)
        avg_conf = (
            sum(r.confidence for r in results) / kept_count
            if kept_count > 0
            else 0.0
        )
        self._ocr_results = results
        self._export_btn.setEnabled(True)
        self._state_machine.ocr_done()
        self._progress_bar.setVisible(False)
        filtered_note = (
            f"  ({raw_count - kept_count} filtered)" if raw_count != kept_count else ""
        )
        self._status_bar.showMessage(
            f"OCR complete: {kept_count} block(s) kept{filtered_note}"
            f"  |  avg confidence: {avg_conf:.2f}"
        )
        self._populate_preview(results)
        self._update_ui_for_state(AppState.IDLE)

    @Slot(str)
    def _on_ocr_error(self, message: str) -> None:
        logger.error("MainWindow: OCR error: %s", message)
        self._state_machine.trigger("error")
        self._progress_bar.setVisible(False)
        self._status_bar.showMessage(f"OCR error: {message}")
        QMessageBox.critical(self, "OCR Error", message)
        self._update_ui_for_state(AppState.IDLE)

    @Slot(int, int)
    def _on_ocr_progress(self, done: int, total: int) -> None:
        self._status_bar.showMessage(f"OCR: processing image {done}/{total}…")
        if total > 0:
            self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(done)
            self._progress_bar.setVisible(True)

    @Slot()
    def _trigger_export(self) -> None:
        if not self._ocr_results or not self._state_machine.export():
            return

        fmt = self._export_fmt_combo.currentData()
        is_epub = fmt == "epub"
        output_dir = self._cfg.get("epub_output_dir", str(Path.home()))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_name = (
            self._session.root.name if self._session else "export"
        )
        _EXT_MAP = {"epub": "epub", "txt": "txt", "md": "md"}
        _FILTER_MAP = {
            "epub": "EPUB files (*.epub)",
            "txt": "Text files (*.txt)",
            "md": "Markdown files (*.md)",
        }
        _TITLE_MAP = {
            "epub": "Save EPUB",
            "txt": "Save Plain Text",
            "md": "Save Markdown",
        }
        ext = _EXT_MAP.get(fmt, "epub")
        default_name = f"{session_name}_{timestamp}.{ext}"
        file_filter = _FILTER_MAP.get(fmt, "EPUB files (*.epub)")
        dialog_title = _TITLE_MAP.get(fmt, "Save EPUB")
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            dialog_title,
            str(Path(output_dir) / default_name),
            file_filter,
        )
        if not save_path:
            self._state_machine.cancel()
            self._update_ui_for_state(AppState.IDLE)
            return

        # Persist the chosen directory for next time.
        chosen_dir = str(Path(save_path).parent)
        self._config.set("epub_output_dir", chosen_dir)
        self._config.save()
        self._cfg = self._config._data

        chapters = self._build_chapters_from_results()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setVisible(True)
        try:
            _FORMATTER_MAP = {
                "epub": EpubFormatter,
                "txt": PlainTextFormatter,
                "md": MarkdownFormatter,
            }
            formatter = _FORMATTER_MAP.get(fmt, EpubFormatter)()
            output_bytes = formatter.format(chapters, self._cfg)
            Path(save_path).write_bytes(output_bytes)
            logger.info("MainWindow: %s saved to '%s'.", ext.upper(), save_path)
            self._last_export_path = save_path
            self._progress_bar.setVisible(False)
            self._status_bar.showMessage(f"{ext.upper()} saved: {Path(save_path).name}")
            self._open_folder_btn.setVisible(True)
            self._state_machine.export_done()
        except Exception as exc:
            logger.error("MainWindow: export failed: %s", exc)
            self._progress_bar.setVisible(False)
            QMessageBox.critical(self, "Export Error", str(exc))
            self._state_machine.trigger("error")
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _trigger_cancel(self) -> None:
        if self._capture_overlay is not None:
            self._capture_overlay.close()
            self._capture_overlay = None
        self._state_machine.cancel()
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _toggle_border_overlay(self) -> None:
        if self._border_overlay.isVisible():
            self._border_overlay.hide()
        else:
            if self._capture_region is not None:
                self._border_overlay.show()

    def _install_log_handler(self) -> None:
        """Attach a QtLogHandler to the root logger for the log panel."""
        self._log_handler = QtLogHandler(level=logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
                                datefmt="%H:%M:%S")
        self._log_handler.setFormatter(fmt)
        self._log_handler.emitter.message_logged.connect(self._append_log)
        logging.getLogger().addHandler(self._log_handler)

    @Slot(bool)
    def _toggle_log_panel(self, checked: bool) -> None:
        """Show or hide the log panel; keep menu action label in sync."""
        self._log_panel.setVisible(checked)
        self._toggle_log_action.setText(
            "Hide Log Panel" if checked else "Show Log Panel"
        )

    @Slot(str)
    def _append_log(self, message: str) -> None:
        """Append *message* to the log panel and auto-scroll to bottom."""
        self._log_panel.append(message)
        sb = self._log_panel.verticalScrollBar()
        sb.setValue(sb.maximum())

    @Slot()
    def _on_open_export_folder(self) -> None:
        """Open the folder containing the last exported EPUB in Explorer."""
        if not self._last_export_path:
            return
        folder = str(Path(self._last_export_path).parent)
        try:
            os.startfile(folder)
        except OSError as exc:
            logger.warning("MainWindow: could not open folder '%s': %s", folder, exc)

    @Slot(bool)
    def _toggle_dark_mode(self, checked: bool) -> None:
        """Persist dark-mode preference and apply immediately."""
        self._config.set("dark_mode", checked)
        self._config.save()
        self._apply_theme(checked)

    def _apply_theme(self, dark: bool) -> None:
        """Apply a dark or light palette to the QApplication instance."""
        app = QApplication.instance()
        if app is None:
            return
        if dark:
            app.setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(30, 30, 30))
            palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
            palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
            app.setPalette(palette)
        else:
            app.setStyle("Fusion")
            app.setPalette(app.style().standardPalette())

    @Slot()
    def _open_about(self) -> None:
        """Show the About dialog."""
        AboutDialog(parent=self).exec()

    @Slot()
    def _open_settings(self) -> None:
        """Open the Settings dialog; reload live config dict on accept."""
        dlg = SettingsDialog(self._config, parent=self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self._cfg = self._config._data
            self._hotkeys.reload(self._cfg)
            self._apply_preview_font_size(int(self._cfg.get("preview_font_size", 11)))
            self._update_pipeline_mode_label()
            logger.info("MainWindow: settings updated.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_pipeline_mode_label(self) -> None:
        """Refresh the pipeline mode permanent status bar label from config."""
        mode = str(self._cfg.get("ocr_pipeline_mode", "LOCAL_FAST"))
        self._pipeline_mode_label.setText(f"Mode: {mode}")

    def _apply_preview_font_size(self, size: int) -> None:
        """Set the font point size on the OCR results preview pane."""
        font = self._preview_pane.font()
        font.setPointSize(max(8, min(size, 24)))
        self._preview_pane.setFont(font)

    _MAX_RECENT = 5

    def _record_recent_session(self, path: str) -> None:
        """Prepend path to recent_sessions list, cap at _MAX_RECENT, persist."""
        recent: list = list(self._config.get("recent_sessions", []))  # type: ignore[arg-type]
        if not isinstance(recent, list):
            recent = []
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = recent[: self._MAX_RECENT]
        self._config.set("recent_sessions", recent)
        self._config.save()
        self._cfg = self._config._data
        self._update_recent_menu()

    def _update_recent_menu(self) -> None:
        """Rebuild the Recent Sessions submenu from config."""
        self._recent_menu.clear()
        recent: list = list(self._config.get("recent_sessions", []))  # type: ignore[arg-type]
        if not isinstance(recent, list):
            recent = []
        if not recent:
            placeholder = QAction("(no recent sessions)", self)
            placeholder.setEnabled(False)
            self._recent_menu.addAction(placeholder)
            return
        for path in recent:
            action = QAction(str(path), self)
            action.triggered.connect(
                lambda checked=False, p=path: self._open_recent_session(p)
            )
            self._recent_menu.addAction(action)

    @Slot()
    def _open_recent_session(self, path: str) -> None:
        """Resume the session at *path* directly (skip SessionDialog)."""
        if not self._state_machine.is_idle:
            return
        session_root = Path(path)
        if not session_root.exists():
            QMessageBox.warning(
                self,
                "Session not found",
                f"The session folder no longer exists:\n{path}",
            )
            return
        self._session = CaptureSession(session_root, resume=True)
        self._ocr_results = []
        self._clear_preview()
        self._load_notes()
        self._record_recent_session(path)
        self._update_session_labels()
        self._export_btn.setEnabled(False)
        self._status_bar.showMessage(
            f"Session resumed: {path}  |  Section {self._session.current_folder}"
        )
        self._update_ui_for_state(AppState.IDLE)

    @Slot()
    def _reset_capture_count(self) -> None:
        """Clear OCR results, reset count label, disable export, clear preview."""
        if not self._state_machine.is_idle or self._session is None:
            return
        self._ocr_results = []
        self._count_label.setText("0")
        self._export_btn.setEnabled(False)
        self._clear_preview()
        self._status_bar.showMessage("Capture count reset.")
        logger.info("MainWindow: capture count reset.")

    def _load_notes(self) -> None:
        """Load notes.txt from the session root into the notes widget."""
        if self._session is None:
            self._notes_edit.setEnabled(False)
            self._notes_edit.blockSignals(True)
            self._notes_edit.setPlainText("")
            self._notes_edit.blockSignals(False)
            return
        self._notes_edit.setEnabled(True)
        notes_path = self._session.root / "notes.txt"
        self._notes_edit.blockSignals(True)
        try:
            text = notes_path.read_text(encoding="utf-8") if notes_path.exists() else ""
        except OSError:
            text = ""
        self._notes_edit.setPlainText(text)
        self._notes_edit.blockSignals(False)

    @Slot()
    def _on_notes_changed(self) -> None:
        """Auto-save notes to session_root/notes.txt on every change."""
        if self._session is None:
            return
        notes_path = self._session.root / "notes.txt"
        try:
            notes_path.write_text(
                self._notes_edit.toPlainText(), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("MainWindow: could not save notes: %s", exc)

    def _populate_preview(self, results: list[OCRResult]) -> None:
        """Fill the preview pane with OCR results grouped by image_id."""
        if not results:
            self._preview_pane.setPlainText("")
            self._preview_label.setText("<b>OCR Results:</b> 0 blocks")
            return

        lines: list[str] = []
        current_id: str | None = None
        for r in results:
            if r.image_id and r.image_id != current_id:
                current_id = r.image_id
                lines.append(f"── {current_id} ──")
            lines.append(r.text)

        self._preview_pane.setPlainText("\n".join(lines))
        n = len(results)
        self._preview_label.setText(f"<b>OCR Results:</b> {n} block{'s' if n != 1 else ''}")
        self._copy_btn.setEnabled(True)

    def _clear_preview(self) -> None:
        """Clear the preview pane and reset its label."""
        self._preview_pane.setPlainText("")
        self._preview_label.setText("<b>OCR Results:</b> —")
        self._copy_btn.setEnabled(False)

    @Slot()
    def _copy_results_to_clipboard(self) -> None:
        """Copy the current preview text to the system clipboard."""
        text = self._preview_pane.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._status_bar.showMessage("OCR text copied to clipboard.", 3000)

    def _build_chapters_from_results(self) -> list[Chapter]:
        """Group OCRResults into Chapter objects by image_id prefix."""
        if self._session is None:
            return [Chapter(number=1, results=self._ocr_results)]

        chapters_map: dict[int, list[OCRResult]] = {}
        for r in self._ocr_results:
            for fn in range(1, self._session.current_folder + 1):
                folder_path = self._session.root / str(fn)
                if any(
                    folder_path / f"{r.image_id}.png" == p
                    or r.image_id.startswith(str(fn) + "/")
                    for p in [folder_path / f"{r.image_id}.png"]
                ):
                    chapters_map.setdefault(fn, []).append(r)
                    break
            else:
                chapters_map.setdefault(1, []).append(r)

        return [
            Chapter(number=fn, results=results)
            for fn, results in sorted(chapters_map.items(), key=lambda x: x[0])
        ]

    def _update_session_labels(self) -> None:
        if self._session is None:
            return
        self._session_label.setText(str(self._session.root))
        self._section_label.setText(str(self._session.current_folder))
        self._update_count_label()

    def _update_count_label(self) -> None:
        if self._session is None:
            self._count_label.setText("0")
            return
        total = self._session.total_images()
        current = self._session.image_count(self._session.current_folder)
        self._count_label.setText(
            f"{total} total  (section: {current})"
        )

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._hotkeys.stop()
        logging.getLogger().removeHandler(self._log_handler)
        self._border_overlay.close()
        if self._capture_overlay is not None:
            self._capture_overlay.close()
        event.accept()
