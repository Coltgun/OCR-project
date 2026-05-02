"""
GUI overlay widgets for the capture pipeline.

CaptureOverlay     — full-screen rubber-band region selector.
RegionBorderOverlay — persistent always-on-top border around the capture area.

Both widgets use PySide6 Qt6. They require a running QApplication.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QRubberBand, QWidget
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class CaptureOverlay(QWidget):
    """Full-screen, transparent rubber-band selector.

    Shows a full-screen window. The user drags to select a rectangular region.
    On mouse release, emits region_selected(QRect) and closes itself.
    Pressing Escape cancels and emits cancelled().

    Signals:
        region_selected(QRect): Emitted when the user completes a drag.
        cancelled():            Emitted when the user presses Escape.
    """

    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._origin = QPoint()

    def show_fullscreen(self) -> None:
        """Show the overlay covering the full primary screen."""
        self.showFullScreen()

    def mousePressEvent(self, event) -> None:
        self._origin = event.position().toPoint()
        self._rubber_band.setGeometry(QRect(self._origin, QSize()))
        self._rubber_band.show()

    def mouseMoveEvent(self, event) -> None:
        self._rubber_band.setGeometry(
            QRect(self._origin, event.position().toPoint()).normalized()
        )

    def mouseReleaseEvent(self, event) -> None:
        region = QRect(self._origin, event.position().toPoint()).normalized()
        self._rubber_band.hide()
        self.close()
        if region.width() > 0 and region.height() > 0:
            logger.info(
                "CaptureOverlay: region selected: (%d,%d) %dx%d",
                region.x(), region.y(), region.width(), region.height(),
            )
            self.region_selected.emit(region)
        else:
            logger.debug("CaptureOverlay: zero-size region ignored, emitting cancelled.")
            self.cancelled.emit()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._rubber_band.hide()
            self.close()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)


class RegionBorderOverlay(QWidget):
    """Persistent always-on-top border drawn around the current capture region.

    Non-interactive (mouse events pass through). Toggled visible/hidden with F7.
    Call update_region() to reposition whenever the capture region changes.

    Args:
        border_color: RGBA QColor for the border. Defaults to semi-transparent orange.
        border_width: Border line width in pixels. Defaults to 3.
    """

    def __init__(
        self,
        border_color: QColor | None = None,
        border_width: int = 3,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._border_color = border_color or QColor(255, 100, 0, 200)
        self._border_width = border_width

    def update_region(self, x: int, y: int, w: int, h: int) -> None:
        """Reposition the overlay window to exactly cover the capture region.

        Args:
            x: Left edge in screen coordinates.
            y: Top edge in screen coordinates.
            w: Width in pixels.
            h: Height in pixels.
        """
        self.setGeometry(x, y, w, h)
        self.update()
        logger.debug(
            "RegionBorderOverlay: geometry set to (%d,%d) %dx%d", x, y, w, h
        )

    def update_region_from_qrect(self, rect: QRect) -> None:
        """Convenience overload accepting a QRect."""
        self.update_region(rect.x(), rect.y(), rect.width(), rect.height())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        pen = QPen(self._border_color, self._border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
