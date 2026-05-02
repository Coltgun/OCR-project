"""
SettingsDialog — application settings editor.

Sections:
  Pipeline    — mode selector (QComboBox), dedup/correction thresholds
  API Keys    — OpenRouter API key (password field), Ollama base URL
  VRAM        — VRAM tier selector (8gb / 16gb)
  Capture     — working root dir
  Hotkeys     — 3-column QTableWidget (Action | Default | Override) for each binding

Reads current values from ConfigManager on open; writes back and calls
save() only when the user accepts.  Cancel leaves config unchanged.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from capture.hotkeys import _DEFAULT_BINDINGS, _PYNPUT_KEY_MAP
from ocr.pipeline import PIPELINE_MODES
from utils.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Modal settings dialog.

    After exec() returns QDialog.Accepted the config has been saved to disk.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config_manager

        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)
        self.setModal(True)

        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        tabs = QTabWidget()
        tabs.addTab(self._build_pipeline_tab(), "Pipeline")
        tabs.addTab(self._build_api_tab(), "API Keys")
        tabs.addTab(self._build_vram_tab(), "VRAM")
        tabs.addTab(self._build_capture_tab(), "Capture")
        tabs.addTab(self._build_hotkeys_tab(), "Hotkeys")
        root.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # --- Pipeline tab ---------------------------------------------------

    def _build_pipeline_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        # Mode selector
        mode_group = QGroupBox("Pipeline Mode")
        mode_form = QFormLayout(mode_group)
        self._mode_combo = QComboBox()
        for mode in PIPELINE_MODES:
            self._mode_combo.addItem(mode)
        mode_form.addRow("Active mode:", self._mode_combo)
        layout.addWidget(mode_group)

        # Deduplication thresholds
        dedup_group = QGroupBox("Deduplication")
        dedup_form = QFormLayout(dedup_group)

        self._minhash_threshold = self._make_double_spin(0.0, 1.0, 0.01, 2)
        dedup_form.addRow("MinHash threshold:", self._minhash_threshold)

        self._embedding_threshold = self._make_double_spin(0.0, 1.0, 0.01, 2)
        dedup_form.addRow("Embedding threshold:", self._embedding_threshold)

        layout.addWidget(dedup_group)

        # OCR confidence filter
        confidence_group = QGroupBox("OCR Confidence Filter")
        confidence_form = QFormLayout(confidence_group)

        self._ocr_min_confidence = self._make_double_spin(0.0, 1.0, 0.05, 2)
        confidence_form.addRow("Min confidence (discard <):", self._ocr_min_confidence)

        layout.addWidget(confidence_group)

        # Hybrid correction thresholds
        hybrid_group = QGroupBox("Hybrid Correction Thresholds")
        hybrid_form = QFormLayout(hybrid_group)

        self._hybrid_high = self._make_double_spin(0.0, 1.0, 0.01, 2)
        hybrid_form.addRow("High confidence (pass-through ≥):", self._hybrid_high)

        self._hybrid_low = self._make_double_spin(0.0, 1.0, 0.01, 2)
        hybrid_form.addRow("Low confidence (LLM tier <):", self._hybrid_low)

        layout.addWidget(hybrid_group)
        layout.addStretch()
        return widget

    # --- API Keys tab ---------------------------------------------------

    def _build_api_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        or_group = QGroupBox("OpenRouter")
        or_form = QFormLayout(or_group)

        self._openrouter_key = QLineEdit()
        self._openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._openrouter_key.setPlaceholderText("sk-or-…")
        or_form.addRow("API key:", self._openrouter_key)

        self._openrouter_model = QLineEdit()
        self._openrouter_model.setPlaceholderText("qwen/qwen-2.5-7b-instruct")
        or_form.addRow("Default model:", self._openrouter_model)

        self._openrouter_base_url = QLineEdit()
        self._openrouter_base_url.setPlaceholderText("https://openrouter.ai/api/v1")
        or_form.addRow("Base URL:", self._openrouter_base_url)

        layout.addWidget(or_group)

        ollama_group = QGroupBox("Ollama (local LLM)")
        ollama_form = QFormLayout(ollama_group)

        self._llm_base_url = QLineEdit()
        self._llm_base_url.setPlaceholderText("http://localhost:11434/v1")
        ollama_form.addRow("Base URL:", self._llm_base_url)

        self._llm_model = QLineEdit()
        self._llm_model.setPlaceholderText("qwen2.5:7b-instruct-q4_K_M")
        ollama_form.addRow("Model:", self._llm_model)

        layout.addWidget(ollama_group)
        layout.addStretch()
        return widget

    # --- VRAM tab -------------------------------------------------------

    def _build_vram_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        vram_group = QGroupBox("VRAM Tier")
        vram_form = QFormLayout(vram_group)

        self._vram_combo = QComboBox()
        self._vram_combo.addItems(["8gb", "16gb"])
        vram_form.addRow("Tier:", self._vram_combo)

        note = QLabel(
            "8 GB: MacBERT-base, Qwen2.5-7B Q4_K_M, BGE-M3\n"
            "16 GB: MacBERT-large, Qwen2.5-14B Q4_K_M, BGE-M3 resident\n\n"
            "⚠  Changing tier takes effect after restart."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 11px;")
        vram_form.addRow(note)

        layout.addWidget(vram_group)

        bert_group = QGroupBox("BERT Correction")
        bert_form = QFormLayout(bert_group)

        self._bert_batch_size = self._make_int_spin(1, 256)
        bert_form.addRow("Batch size:", self._bert_batch_size)

        self._bert_max_length = self._make_int_spin(32, 512)
        bert_form.addRow("Max token length:", self._bert_max_length)

        layout.addWidget(bert_group)

        embed_group = QGroupBox("Embedding Model")
        embed_form = QFormLayout(embed_group)

        self._embed_batch_size = self._make_int_spin(1, 256)
        embed_form.addRow("Batch size:", self._embed_batch_size)

        layout.addWidget(embed_group)
        layout.addStretch()
        return widget

    # --- Capture tab ----------------------------------------------------

    def _build_capture_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        session_group = QGroupBox("Session Storage")
        session_form = QFormLayout(session_group)

        self._working_root = QLineEdit()
        self._working_root.setPlaceholderText("sessions")
        session_form.addRow("Working root dir:", self._working_root)

        self._export_filename_template = QLineEdit()
        self._export_filename_template.setPlaceholderText("{session}_{timestamp}")
        session_form.addRow("Export filename template:", self._export_filename_template)

        layout.addWidget(session_group)

        auto_group = QGroupBox("Auto Section")
        auto_form = QFormLayout(auto_group)

        self._auto_section_threshold = QSpinBox()
        self._auto_section_threshold.setRange(0, 99)
        self._auto_section_threshold.setValue(0)
        self._auto_section_threshold.setSpecialValueText("Disabled")
        self._auto_section_threshold.setSuffix(" captures")
        auto_form.addRow("New section after:", self._auto_section_threshold)

        layout.addWidget(auto_group)

        display_group = QGroupBox("Display")
        display_form = QFormLayout(display_group)

        self._preview_font_size = QSpinBox()
        self._preview_font_size.setRange(8, 24)
        self._preview_font_size.setValue(11)
        self._preview_font_size.setSuffix(" pt")
        display_form.addRow("Preview font size:", self._preview_font_size)

        layout.addWidget(display_group)
        layout.addStretch()
        return widget

    # --- Hotkeys tab ----------------------------------------------------

    _ACTION_LABELS: dict[str, str] = {
        "capture": "Capture screenshot",
        "new_section": "New section",
        "send_to_ocr": "Run OCR",
        "reset_area": "Select region",
        "toggle_overlay": "Toggle border overlay",
        "cancel": "Cancel",
    }

    def _build_hotkeys_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        self._hotkeys_table = QTableWidget(len(self._ACTION_LABELS), 3)
        self._hotkeys_table.setHorizontalHeaderLabels(["Action", "Default", "Override"])
        self._hotkeys_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._hotkeys_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._hotkeys_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._hotkeys_table.verticalHeader().setVisible(False)
        self._hotkeys_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._hotkeys_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self._hotkey_edits: dict[str, QLineEdit] = {}
        for row, (action, label) in enumerate(self._ACTION_LABELS.items()):
            action_item = QTableWidgetItem(label)
            action_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._hotkeys_table.setItem(row, 0, action_item)

            default_item = QTableWidgetItem(_DEFAULT_BINDINGS.get(action, "").upper())
            default_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            default_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hotkeys_table.setItem(row, 1, default_item)

            edit = QLineEdit()
            edit.setPlaceholderText(_DEFAULT_BINDINGS.get(action, ""))
            edit.setMaxLength(20)
            self._hotkeys_table.setCellWidget(row, 2, edit)
            self._hotkey_edits[action] = edit

        layout.addWidget(self._hotkeys_table)

        _VALID_KEYS = ", ".join(sorted(_PYNPUT_KEY_MAP.keys()))
        note = QLabel(
            f"Valid keys: {_VALID_KEYS}\n"
            "Leave Override blank to use the default. Changes apply when Settings is accepted."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(note)
        layout.addStretch()
        return widget

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_values(self) -> None:
        """Populate all widgets from ConfigManager."""
        cfg = self._config

        # Pipeline
        mode = cfg.get_str("ocr_pipeline_mode", "LOCAL_FAST")
        idx = self._mode_combo.findText(mode)
        self._mode_combo.setCurrentIndex(max(0, idx))

        self._minhash_threshold.setValue(
            float(cfg.get("dedup_threshold", 0.85))
        )
        self._embedding_threshold.setValue(
            float(cfg.get("embedding_threshold", 0.92))
        )
        self._ocr_min_confidence.setValue(
            float(cfg.get("ocr_min_confidence", 0.0))
        )
        self._hybrid_high.setValue(
            float(cfg.get("hybrid_high_threshold", 0.90))
        )
        self._hybrid_low.setValue(
            float(cfg.get("hybrid_low_threshold", 0.70))
        )

        # API
        self._openrouter_key.setText(
            cfg.get_str("openrouter_api_key", "")
        )
        self._openrouter_model.setText(
            cfg.get_str("openrouter_model", "")
        )
        self._openrouter_base_url.setText(
            cfg.get_str("openrouter_base_url", "")
        )
        self._llm_base_url.setText(
            cfg.get_str("llm_base_url", "")
        )
        self._llm_model.setText(
            cfg.get_str("llm_model", "")
        )

        # VRAM
        vram = cfg.get_str("vram_tier", "8gb")
        vidx = self._vram_combo.findText(vram)
        self._vram_combo.setCurrentIndex(max(0, vidx))

        self._bert_batch_size.setValue(
            int(cfg.get("bert_batch_size", 32))
        )
        self._bert_max_length.setValue(
            int(cfg.get("bert_max_length", 128))
        )
        self._embed_batch_size.setValue(
            int(cfg.get("embedding_batch_size", 32))
        )

        # Capture
        self._working_root.setText(
            cfg.get_str("working_root_dir", "sessions")
        )
        self._export_filename_template.setText(
            cfg.get_str("export_filename_template", "{session}_{timestamp}")
        )
        self._auto_section_threshold.setValue(
            int(cfg.get("auto_new_section_threshold", 0))
        )
        self._preview_font_size.setValue(
            int(cfg.get("preview_font_size", 11))
        )

        # Hotkeys
        saved_bindings: dict = cfg.get("keybindings", {})  # type: ignore[assignment]
        if not isinstance(saved_bindings, dict):
            saved_bindings = {}
        for action, edit in self._hotkey_edits.items():
            edit.setText(str(saved_bindings.get(action, "")))

    def _save_values(self) -> None:
        """Write widget values back to ConfigManager and persist."""
        cfg = self._config

        cfg.set("ocr_pipeline_mode", self._mode_combo.currentText())
        cfg.set("dedup_threshold", self._minhash_threshold.value())
        cfg.set("embedding_threshold", self._embedding_threshold.value())
        cfg.set("ocr_min_confidence", self._ocr_min_confidence.value())
        cfg.set("hybrid_high_threshold", self._hybrid_high.value())
        cfg.set("hybrid_low_threshold", self._hybrid_low.value())

        cfg.set("openrouter_api_key", self._openrouter_key.text().strip())
        cfg.set("openrouter_model", self._openrouter_model.text().strip())
        cfg.set("openrouter_base_url", self._openrouter_base_url.text().strip())
        cfg.set("llm_base_url", self._llm_base_url.text().strip())
        cfg.set("llm_model", self._llm_model.text().strip())

        cfg.set("vram_tier", self._vram_combo.currentText())
        cfg.set("bert_batch_size", self._bert_batch_size.value())
        cfg.set("bert_max_length", self._bert_max_length.value())
        cfg.set("embedding_batch_size", self._embed_batch_size.value())

        cfg.set("working_root_dir", self._working_root.text().strip() or "sessions")
        cfg.set(
            "export_filename_template",
            self._export_filename_template.text().strip() or "{session}_{timestamp}",
        )
        cfg.set("auto_new_section_threshold", self._auto_section_threshold.value())
        cfg.set("preview_font_size", self._preview_font_size.value())

        # Hotkeys
        bindings: dict[str, str] = {}
        for action, edit in self._hotkey_edits.items():
            val = edit.text().strip().lower()
            if val:
                bindings[action] = val
        cfg.set("keybindings", bindings)

        cfg.save()
        logger.info("SettingsDialog: config saved.")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        """Validate thresholds, save, and close."""
        high = self._hybrid_high.value()
        low = self._hybrid_low.value()
        if low >= high:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Invalid Thresholds",
                f"Hybrid low threshold ({low:.2f}) must be less than "
                f"high threshold ({high:.2f}).",
            )
            return

        self._save_values()
        self.accept()

    # ------------------------------------------------------------------
    # Widget factories
    # ------------------------------------------------------------------

    @staticmethod
    def _make_double_spin(
        min_val: float, max_val: float, step: float, decimals: int
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        return spin

    @staticmethod
    def _make_int_spin(min_val: int, max_val: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        return spin
