# =============================================================================
# SPRINGHALL_UI.PY — MAIN UI CONTROLLER
# =============================================================================
# This is the main UI file for the SpringHall reverb pedal interface.
#
# TABLE OF CONTENTS:
# -----------------------------------------------------------------------------
#  1. Imports & Globals
#  2. Helper Functions
#  3. Custom Widgets
#     3.1 AnimatedButton
#     3.2 AnimatedSlider
#     3.3 PNGDial / RingDial
#     3.4 ClickableLabel
#  4. Popups & Dialogs
#     4.1 DarkMessageDialog
#     4.2 SavePresetDialog
#     4.3 SuccessMessageDialog
#     4.4 CustomMessageDialog
#  5. Presets Window
#  6. SpringHallUI Main Window
#     6.1 Constructor & Initialization
#     6.2 Compose UI Layout
#     6.3 Edit Preset Page
#     6.4 System Menu
#     6.5 Modulation Window
#     6.6 Preset Logic (Save, Load, Next Slot)
#  7. Entry Points for Customization (🔧)
# -----------------------------------------------------------------------------
# To add a new module, navigate to section 7 or look for "🔧 ENTRY POINT".
# =============================================================================


# springhall_ui.py
# ---------------------------------------------------------------------------
# Reverb pedal UI with dark theme, compact Presets window, dimming overlay,
# animated / static background (pre‑scaled to 1595 × 740 px), semi‑transparent
# slider bar, dark pop‑ups, and a NEW hamburger‑menu tool‑button that shows a
# styled drop‑down with common reverb‑pedal functions.
# ---------------------------------------------------------------------------
 

import sys                               # needed for LED positioning
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from datetime import datetime
from typing import Optional
from PIL import Image
from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import QGraphicsOpacityEffect
 
slider_widget_map = {}
knob_widget_map = {}
slider_label_map  = {}
mod_value_map = {
    "Speed": 0.0,
    "Shape": 0.0,
    "Phase": 0.0,
    "Spread": 0.0,
}

bic_value_map = {
    "Rate": 0.0,
    "Depth": 0.0,
    "Tone": 0.0,
    "Mix": 0.0,
}

ech_value_map = {
    "Time": 0.0,
    "FB": 0.0,
    "Tone": 0.0,
    "Mod": 0.0,
    "Mix": 0.0,
    "Level": 0.0,
}
 
# Make sure RingDial is defined BEFORE PNGDial
class RingDial(QtWidgets.QDial):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setRange(0, 100)
        self.setNotchesVisible(False)
        self.setFixedSize(84, 84)
        self.valueChanged.connect(self.update)
 
        self.setStyleSheet("""
            QDial { background:transparent; }
            QDial::handle {
                background:#222;
                border:1px solid #000;
                width:14px; height:14px;
                border-radius:7px;
                margin:-7px;
            }
            QDial::handle:hover { background:#555; }
        """)
 
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)  # ← Add this line
 
        cx, cy = self.width() / 2, self.height() / 2
        center = QtCore.QPointF(cx, cy)
        radius = min(self.width(), self.height()) / 2 - 4
 
        # Black face
        grad = QtGui.QRadialGradient(center, radius, center)
        grad.setColorAt(0.0, QtGui.QColor(30, 30, 30))
        grad.setColorAt(1.0, QtGui.QColor(5, 5, 5))
        painter.setBrush(grad)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(center, radius, radius)
 
        # Status ring (270° sweep)
        ratio = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
        sweep_deg = 270 * ratio
        start_deg = 225
        pen = QtGui.QPen(QtGui.QColor(50, 130, 255, 200))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawArc(
            QtCore.QRect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2)),
            int(start_deg * 16),
            int(-sweep_deg * 16)
        )
 
        # LED indicator (moves with ring)
        led_r = 3
        led_angle_deg = start_deg - sweep_deg  # LED angle matches ring progress
        led_angle = math.radians(led_angle_deg)
        led_dist = radius - 8
        led_x = cx + led_dist * math.cos(led_angle)
        led_y = cy - led_dist * math.sin(led_angle)
        led_on = QtGui.QColor(255, 255, 255, 220)  # White LED when on
        led_off = QtGui.QColor(60, 60, 60, 120)     # Dim gray when off
        painter.setBrush(led_on if self.value() else led_off)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(QtCore.QPointF(led_x, led_y), led_r, led_r)
 

# ──────────────────────────────────────────────
# CUSTOM WIDGET: PNGDial
# ──────────────────────────────────────────────
class PNGDial(RingDial):
    """Dial that reuses RingDial’s ring/LED paint, but overlays a PNG knob cap.
       Each instance can have its own PNG file and angle offset."""
 
    def __init__(self, *args,
                 img_path: str = "assets/knob_base.png",
                 angle_offset: int = 90,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.knob_img     = QtGui.QPixmap(img_path)  # load after QApplication
        self.angle_offset = angle_offset             # per‑knob rotation tweak
 
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        # 1) draw the ring + LED
        super().paintEvent(event)
 
        # 2) draw the PNG knob cap, rotated to match dial value + offset
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)  # ← Add this line
 
        dial_size = min(self.width(), self.height())
        knob_size = int(dial_size * 0.82)           # knob ≈ 82 % of dial
        knob = self.knob_img.scaled(
            knob_size, knob_size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
 
        sweep_deg  = 270                            # total sweep
        start_deg  = -225                           # 0 % position
        rot_deg    = start_deg + (self.value() / 100) * sweep_deg
        rot_deg   += self.angle_offset              # per‑instance tweak
 
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(rot_deg)
        painter.translate(-knob.width() / 2, -knob.height() / 2)
        painter.drawPixmap(0, 0, knob)
        painter.end()
 
# Your main window class example (adjust to your actual main window class)
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        # Your init code...
 
    def closeEvent(self, e):
        self.save_bic_presets()
        self.save_mod_presets()
        self.save_ech_presets()

        if self.parent():
            self.parent().close()

        super().closeEvent(e)
 
 
 
def sync_controls(name, value, source):
    if source == "slider":
        knob = knob_widget_map.get(name)
        if knob and knob.value() != value // 10:
            knob.blockSignals(True)
            knob.setValue(value // 10)
            knob.blockSignals(False)
 
    elif source == "knob":
        slider = slider_widget_map.get(name)
        if slider and slider.value() != value * 10:
            slider.blockSignals(True)
            slider.setValue(value * 10)
            slider.blockSignals(False)
            label = slider_label_map.get(name)
            if label:
                label.setText(f"{value:02}")
            # Commenting out update and emit for test
            # slider.update()
            # slider.valueChanged.emit(value * 10)
 
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_font(pt: int, *, weight: int = QtGui.QFont.Bold, track: Optional[float] = None):
    f = QtGui.QFont("Segoe UI", pt, weight)
    if track is not None:
        f.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, track)
    return f
 
 
class ClickableLabel(QtWidgets.QLabel):
    clicked = QtCore.pyqtSignal()
 
    def mousePressEvent(self, e):
        if e.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)
 
 
# ---------------------------------------------------------------------------
# Background widget – GIF / PNG scaled to 1595 × 740
# ---------------------------------------------------------------------------
class BackgroundWidget(QtWidgets.QWidget):
    """Draw an animated GIF, a PNG, or fallback to black, pre‑scaled to 1595×740."""
 
    TARGET_W, TARGET_H = 1595, 740
 
    def __init__(self):
        super().__init__()
        self._movie: Optional[QtGui.QMovie] = None
        self._pix: Optional[QtGui.QPixmap] = None
 
        tgt_size = QtCore.QSize(self.TARGET_W, self.TARGET_H)
 
        # Animated GIF
        if os.path.exists("background.gif"):
            self._movie = QtGui.QMovie("background.gif", parent=self)
            self._movie.setCacheMode(QtGui.QMovie.CacheAll)
            self._movie.setScaledSize(tgt_size)
            self._movie.frameChanged.connect(self.update)
            self._movie.start()
 
        # Static PNG
        elif os.path.exists("background.png"):
            img = Image.open("background.png").convert("RGBA")
            img = img.resize((self.TARGET_W, self.TARGET_H), Image.LANCZOS)
            data = img.tobytes("raw", "RGBA")
            qimg = QtGui.QImage(data, img.width, img.height, QtGui.QImage.Format_RGBA8888)
            self._pix = QtGui.QPixmap.fromImage(qimg)
 
    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        if self._movie and self._movie.state() == QtGui.QMovie.Running:
            frame = self._movie.currentPixmap()
            if not frame.isNull():
                p.drawPixmap(self.rect(), frame)
        elif self._pix and not self._pix.isNull():
            p.drawPixmap(self.rect(), self._pix)
        else:
            p.fillRect(self.rect(), QtGui.QColor("#000"))
 
 
# ---------------------------------------------------------------------------
# Animated button & slider
# ---------------------------------------------------------------------------
class AnimatedButton(QtWidgets.QPushButton):
    """Push‑button with a quick fade animation."""
 
    def __init__(self, text):
        super().__init__(text)
        eff = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        self.anim = QtCore.QPropertyAnimation(eff, b"opacity", self, duration=150)
        self.setStyleSheet(
            """
            QPushButton { color:white; background:rgba(30,30,30,180); border:none;
                          padding:8px 14px; border-radius:4px; font-size:11px; }
            QPushButton:hover { background:rgba(50,50,50,230); }
        """
        )
        self.setFixedHeight(32)
 
    def mousePressEvent(self, e):
        self.anim.stop(); self.anim.setStartValue(1.0); self.anim.setEndValue(0.4); self.anim.start()
        super().mousePressEvent(e)
 
    def mouseReleaseEvent(self, e):
        self.anim.stop(); self.anim.setStartValue(0.4); self.anim.setEndValue(1.0); self.anim.start()
        super().mouseReleaseEvent(e)
 
 
class AnimatedSlider(QtWidgets.QSlider):
    """Slider enlarges groove / handle while dragging."""
 
    def __init__(self, orientation, color="#0055ff"):
        super().__init__(orientation)
        self.color = color
        self.default_style = f"""
            QSlider::groove:horizontal {{height:4px; background:#888;}}
            QSlider::sub-page:horizontal {{background:{self.color};}}
            QSlider::handle:horizontal {{background:{self.color}; width:10px; border-radius:5px;}}
        """
        self.expanded_style = f"""
            QSlider::groove:horizontal {{height:10px; background:#888;}}
            QSlider::sub-page:horizontal {{background:{self.color};}}
            QSlider::handle:horizontal {{background:{self.color}; width:24px; border-radius:12px;}}
        """
        self.setStyleSheet(self.default_style)
 
    def mousePressEvent(self, e):
        self.setStyleSheet(self.expanded_style)
        super().mousePressEvent(e)
 
    def mouseReleaseEvent(self, e):
        self.setStyleSheet(self.default_style)
        super().mouseReleaseEvent(e)
 
 
# ---------------------------------------------------------------------------
# Dark pop‑up dialogs
# ---------------------------------------------------------------------------
class DarkMessageDialog(QtWidgets.QDialog):
    """Generic OK dialog matching the dark GUI theme."""
 
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(460, 220)
 
        self.setStyleSheet(
            """
            QDialog  { background:#121212; color:white; border-radius:10px; }
            QLabel   { font-size:16px; padding:36px 36px 24px 36px; qproperty-alignment:'AlignCenter'; color:white; }
            QPushButton {
                background:#3f7cff; border:none; border-radius:6px;
                padding:16px 36px; color:white; font-weight:bold; font-size:16px;
                min-width:120px; margin-bottom:28px;
            }
            QPushButton:hover  { background:#5591ff; }
            QPushButton:pressed{ background:#2c62cc; }
        """
        )
 
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(20)
 
        lay.addWidget(QtWidgets.QLabel(message))
 
        btn_ok = QtWidgets.QPushButton("OK")
        btn_ok.setFixedHeight(48)
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
 
        box = QtWidgets.QHBoxLayout()
        box.addStretch(1)
        box.addWidget(btn_ok)
        box.addStretch(1)
        lay.addLayout(box)
 
 
class SavePresetDialog(QtWidgets.QDialog):
    def __init__(self, current_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Preset")
        self.setFixedSize(460, 220)

        self.setStyleSheet(
            """
            QDialog { background:#121212; color:white; border-radius:10px; }
            QLabel  { font-size:14px; margin-bottom:2px; background-color:#121212; padding:4px 8px; }
            QLineEdit {
                background:#1E1E1E; border:1px solid #333; border-radius:5px;
                padding:10px 14px; color:white; font-size:15px; min-height:34px;
                margin-bottom:24px;
            }
            QLineEdit:focus { border:1px solid #3f7cff; background:#262626; }
            QPushButton {
                background:#3f7cff; border:none; border-radius:6px;
                padding:14px 32px; color:white; font-weight:bold; font-size:15px;
            }
            QPushButton:hover  { background:#5591ff; }
            QPushButton:pressed{ background:#2c62cc; }
            """
        )
 
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(24)
 
        lay.addWidget(QtWidgets.QLabel("Enter preset name:"))
        label = lay.itemAt(lay.count() - 1).widget()  # Get the label widget just added
        label.setStyleSheet("background: transparent; padding: 4px 8px;")  # black bg with some padding
        self.line = QtWidgets.QLineEdit(current_name)
        self.line.selectAll()
        self.line.setFocus()
 
        lay.addWidget(self.line)
        lay.addStretch(1)
 
        btn_ok = QtWidgets.QPushButton("Save")
        btn_cancel = QtWidgets.QPushButton("Cancel")
        box = QtWidgets.QHBoxLayout()
        box.addStretch(1)
        box.addWidget(btn_ok)
        box.addWidget(btn_cancel)
        box.addStretch(1)
        lay.addLayout(box)
 
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
 
    def get_values(self):
        return self.line.text().strip()
 
 
class SuccessMessageDialog(QtWidgets.QDialog):
    """Dark‑theme success popup (used after saving presets)."""
 
    def __init__(self, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Success")
        self.setFixedSize(460, 220)
 
        self.setStyleSheet(
            """
            QDialog  { background:#121212; color:white; border-radius:10px; }
            QLabel   { font-size:16px; padding:36px 36px 24px 36px; qproperty-alignment:'AlignCenter'; color:white; }
            QPushButton {
                background:#3f7cff; border:none; border-radius:6px;
                padding:16px 36px; color:white; font-weight:bold; font-size:16px;
                min-width:120px; margin-bottom:28px;
            }
            QPushButton:hover  { background:#5591ff; }
            QPushButton:pressed{ background:#2c62cc; }
        """
        )
 
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 32)
        lay.setSpacing(20)
 
        lay.addWidget(QtWidgets.QLabel(message))
 
        btn_ok = QtWidgets.QPushButton("OK")
        btn_ok.setFixedHeight(48)
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
 
        box = QtWidgets.QHBoxLayout()
        box.addStretch(1)
        box.addWidget(btn_ok)
        box.addStretch(1)
        lay.addLayout(box)
 
 
# ---------------------------------------------------------------------------
# Presets window (unchanged from previous working version)
# ---------------------------------------------------------------------------
class PresetsWindow(QtWidgets.QWidget):
    """Frameless 800×500 window for listing / loading / renaming / deleting presets."""
    preset_selected = QtCore.pyqtSignal(str)
 
    def __init__(self, presets: dict, parent=None):
        super().__init__(parent)
        self.presets = presets
 
        self.setFixedSize(1024, 600)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setStyleSheet("background:#0d0d0d; color:white; border:2px solid #444;")
 
        # ---------------- outer layout ----------------------------------
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
 
        # ----- left navigation panel ------------------------------------
        nav_panel = QtWidgets.QFrame()
        nav_panel.setFixedWidth(200)
        nav_panel.setStyleSheet("background:#131313;")
        nav_lay = QtWidgets.QVBoxLayout(nav_panel)
        nav_lay.setContentsMargins(12, 8, 12, 8)
        nav_lay.setSpacing(2)
 
        hdr = QtWidgets.QLabel("Directory")
        hdr.setFont(make_font(12, weight=QtGui.QFont.Bold))
        nav_lay.addWidget(hdr)
        nav_lay.addSpacing(10)
 
        def heading(text):
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet("color:#888; font-size:9px; letter-spacing:1px;")
            return lbl
 
        nav_lay.addWidget(heading("CLOUD DIRECTORIES"))
 
        def nav_button(text):
            btn = QtWidgets.QPushButton(text)
            btn.setStyleSheet(
                """
                QPushButton { text-align:left; padding:6px 10px; background:transparent;
                              border:none; font-size:13px; color:white; }
                QPushButton:hover { background:#1e1e1e; }
                QPushButton:checked { background:#3f7cff; }
            """
            )
            btn.setCheckable(True)
            return btn
 
        nav_lay.addWidget(nav_button("Presets"))
        nav_lay.addWidget(nav_button("Neural Captures"))
        nav_lay.addWidget(nav_button("Impulse Responses"))
        nav_lay.addSpacing(14)
        nav_lay.addWidget(heading("STARRED AND SHARED WITH ME"))
        nav_lay.addWidget(nav_button("Presets"))
        nav_lay.addWidget(nav_button("Neural Captures"))
        nav_lay.addStretch(1)
        outer.addWidget(nav_panel)
 
        # ----------------------- right/main panel ------------------------
        main = QtWidgets.QFrame()
        main_lay = QtWidgets.QVBoxLayout(main)
        main_lay.setContentsMargins(20, 12, 20, 12)
        main_lay.setSpacing(14)
 
        # top controls row
        top_row = QtWidgets.QHBoxLayout()
        top_row.setSpacing(10)
 
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search")
        self.search_edit.setFixedHeight(28)
        self.search_edit.setStyleSheet(
            """
            QLineEdit { background:#1b1b1b; border:1px solid #333; border-radius:6px;
                        padding-left:26px; color:white; }
            QLineEdit:focus { border:1px solid #3f7cff; }
        """
        )
        icon_lbl = QtWidgets.QLabel(self.search_edit)
        icon_lbl.setPixmap(self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogStart).pixmap(14, 14))
        icon_lbl.move(6, 7)
 
        btn_refresh = AnimatedButton("⟳ Refresh")
        btn_refresh.setFixedWidth(80)
        btn_done = AnimatedButton("✓ Done")
        btn_done.setFixedWidth(70)
        btn_done.clicked.connect(self.close)
 
        top_row.addWidget(self.search_edit, 1)
        top_row.addWidget(btn_refresh)
        top_row.addWidget(btn_done)
        main_lay.addLayout(top_row)
 
        # list
        self.list = QtWidgets.QListWidget()
        self.list.setStyleSheet(
            """
            QListWidget { background:#111; border:1px solid #444; font-size:15px; }
            QListWidget::item { padding:10px 14px; }
            QListWidget::item:selected { background:#3f7cff; color:white; }
        """
        )
        main_lay.addWidget(self.list, 1)
 
        # update / delete
        row_ud = QtWidgets.QHBoxLayout()
        row_ud.addStretch(1)
        self.btn_update = QtWidgets.QPushButton("Update")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        for b in (self.btn_update, self.btn_delete):
            b.setFixedHeight(32)
            b.setEnabled(False)
            b.setStyleSheet(
                """
                QPushButton { background:#3f7cff; border:none; border-radius:6px;
                              color:white; font:bold 13px; padding:8px 18px; }
                QPushButton:hover  { background:#5591ff; }
                QPushButton:pressed{ background:#2c62cc; }
            """
            )
        row_ud.addWidget(self.btn_update)
        row_ud.addWidget(self.btn_delete)
        row_ud.addStretch(1)
        main_lay.addLayout(row_ud)
 
        # bottom close
        btn_close = QtWidgets.QPushButton("Close")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            """
            QPushButton { background:#3f7cff; border:none; border-radius:6px;
                          color:white; font:bold 13px; padding:10px 28px; }
            QPushButton:hover  { background:#5591ff; }
            QPushButton:pressed{ background:#2c62cc; }
        """
        )
        btn_close.clicked.connect(self.close)
        main_lay.addWidget(btn_close)
 
        outer.addWidget(main, 1)
 
        # signals
        self._populate()
        self.search_edit.textChanged.connect(self._filter_list)
        self.list.itemSelectionChanged.connect(self._sel_changed)
        self.list.itemDoubleClicked.connect(self._dbl_clicked)
        self.btn_update.clicked.connect(self._rename)
        self.btn_delete.clicked.connect(self._delete)
 
    # helper methods
    def _populate(self):
        self.list.clear()
        for n, d in self.presets.items():
            item = QtWidgets.QListWidgetItem(f"{n}  [{d.get('position', '')}]")
            pix = QtGui.QPixmap(10, 10)
            pix.fill(QtGui.QColor("#25c75a"))
            item.setIcon(QtGui.QIcon(pix))
            self.list.addItem(item)
        self._filter_list(self.search_edit.text())
 
    def _filter_list(self, text: str):
        t = text.lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(t not in item.text().lower())
 
    def _sel_changed(self):
        ok = self.list.currentItem() is not None
        self.btn_update.setEnabled(ok)
        self.btn_delete.setEnabled(ok)
 
    def _dbl_clicked(self, item):
        name = item.text().split("  [")[0]
        self.preset_selected.emit(name)
        self.close()
 
    def _rename(self):
        item = self.list.currentItem()
        if not item:
            return
        old = item.text().split("  [")[0]
        dlg = SavePresetDialog(old, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        new = dlg.get_values()
        if not new:
            DarkMessageDialog("Invalid Input", "Preset name must be entered.", self).exec_()
            return
        if new != old and new in self.presets:
            DarkMessageDialog("Duplicate Name", f"A preset named '{new}' already exists.", self).exec_()
            return
        self.presets[new] = self.presets.pop(old)
        item.setText(f"{new}  [{self.presets[new].get('position', '')}]")
 
    def _delete(self):
        item = self.list.currentItem()
        if not item:
            return
        name = item.text().split("  [")[0]
        if QtWidgets.QMessageBox.question(
            self,
            "Delete Preset",
            f"Delete preset '{name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        ) == QtWidgets.QMessageBox.Yes:
            self.presets.pop(name, None)
            self.list.takeItem(self.list.row(item))
            self._sel_changed()
 
 
 
 
# ---------------------------------------------------------------------------
# Main SpringHall UI
# ---------------------------------------------------------------------------

import math
import os
from PyQt5 import QtCore, QtGui, QtWidgets


# ──────────────────────────────────────────────
# DIALOG: CustomMessageDialog
# ──────────────────────────────────────────────
class CustomMessageDialog(QtWidgets.QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(360, 180)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)  # force stylesheet background usage

        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 12px;
            }
            QLabel {
                color: #8fc2ff;
                font-family: 'Segoe UI', Helvetica, sans-serif;
                font-size: 14px;
                padding: 20px;
                background-color: #ffffff;  
            }
            QPushButton {
                background-color: #1b1b1b;
                color: #8fc2ff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 600;
                letter-spacing: 1.5px;
            }
            QPushButton:hover {
                background-color: #3f7cff;
                color: white;
            }
            QPushButton:pressed {
                background-color: #2855cc;
            }
        """)

        vbox = QtWidgets.QVBoxLayout(self)
        self.label = QtWidgets.QLabel(message)
        self.label.setWordWrap(True)
        vbox.addWidget(self.label)

        btn = QtWidgets.QPushButton("OK")
        btn.clicked.connect(self.accept)
        btn.setFixedWidth(100)
        btn.setCursor(QtCore.Qt.PointingHandCursor)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        vbox.addLayout(btn_layout)
 

# ──────────────────────────────────────────────
# MAIN UI CLASS: SpringHallUI
# ──────────────────────────────────────────────
class SpringHallUI(QtWidgets.QMainWindow):
    SLIDERS = [
        ("DECAY", 50),
        ("DAMPING", 25.4),
        ("WET/DRY", 26.5),
        ("LEVEL", 50.4),
        ("WEIGHT", 80.6),
        ("DIFFUSION", 50),
    ]
 
    def __init__(self):
        super().__init__()

        import os, json

        # Preset files paths
        self.bic_preset_file = "presets_bic.json"
        self.mod_preset_file = "presets_mod.json"
        self.ech_preset_file = "presets_ech.json"

        # Load presets from disk or create empty dicts
        def load_presets(path):
            if os.path.exists(path):
                with open(path, "r") as f:
                    return json.load(f)
            return {}

        self.bic_presets = load_presets(self.bic_preset_file)
        self.mod_presets = load_presets(self.mod_preset_file)
        self.ech_presets = load_presets(self.ech_preset_file)

        # Save functions
        def save_bic_presets():
            with open(self.bic_preset_file, "w") as f:
                json.dump(self.bic_presets, f)

        def save_mod_presets():
            with open(self.mod_preset_file, "w") as f:
                json.dump(self.mod_presets, f)

        def save_ech_presets():
            with open(self.ech_preset_file, "w") as f:
                json.dump(self.ech_presets, f)

        # Expose save methods so you can call later
        self.save_bic_presets = save_bic_presets
        self.save_mod_presets = save_mod_presets
        self.save_ech_presets = save_ech_presets

        # Track current selected presets
        self.bic_current_preset = None
        self.mod_current_preset = None
        self.ech_current_preset = None

        # ...rest of your UI init code follows here        
        
        # ---- load DS‑Digital font once ----
        font_path = os.path.join(os.path.dirname(__file__), "assets", "DS-DIGI.TTF")
        font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
        if font_id == -1:
            print("Failed to load DS-DIGI font!")
            self.digital_family = "Arial"  # fallback
        else:
            self.digital_family = QtGui.QFontDatabase.applicationFontFamilies(font_id)[0]
            print(f"Loaded DS font family: {self.digital_family}")
       
        self.preset_values = {name.upper(): value for name, value in self.SLIDERS}
        self.setWindowTitle("SpringHall UI")
        self.setFixedSize(1024, 600)
        self.setStyleSheet("color:white; font-family:'Segoe UI',Helvetica,sans-serif;")
        self.setCentralWidget(BackgroundWidget())
 
        self.presets = {}
        self.current_preset_name = "SpringHall"
        self.current_preset_position = "1A"
        self.slider_widgets = []
        self._is_bypassed = False
        
                # ---------- load presets from disk ----------
        self.preset_file = os.path.join(os.path.dirname(__file__), "presets.json")
        if os.path.exists(self.preset_file):
            try:
                with open(self.preset_file, "r") as f:
                    self.presets = json.load(f)
                print(f"Loaded {len(self.presets)} presets from disk.")
            except Exception as e:
                print("Preset‑file read error:", e)
 
        self._compose()
        self._start_clock()
 
    def _compose(self):
        root = QtWidgets.QHBoxLayout(self.centralWidget())
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
 
        nav = QtWidgets.QVBoxLayout()
        nav.setContentsMargins(20, 20, 20, 20)
        nav.setSpacing(10)
        root.addLayout(nav, 0)
 
        def add_btn(text, cb):
            b = QtWidgets.QPushButton(text)
            b.setFixedSize(120, 40)
            b.clicked.connect(cb)
            b.setStyleSheet("""
                QPushButton { background:#1b1b1b; border:none; border-radius:6px; }
                QPushButton:hover { background:#333; }
                QPushButton:pressed { background:#555; }
            """)
            nav.addWidget(b)
            return b
 
        add_btn("MODES",   self._noop)
        add_btn("PRESETS", self._noop)
        add_btn("EDIT",    self._show_edit_preset)
        add_btn("SAVE",    self._noop)
        nav.addStretch(1)
        add_btn("MODULATION", self._noop)
        add_btn("DYNAMICS",   self._noop)
        add_btn("TAP",        self._noop)
 
        label = QtWidgets.QLabel("Main UI Area")
        label.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(label, 1)
 
    def _show_edit_preset(self):
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,220);")
        self.overlay.show()
        self.overlay.raise_()
 
        for name, slider, _ in self.slider_widgets:
            key = "WET/DRY" if name.upper() == "MIX" else name.upper()
            val = self.preset_values.get(key, 50)
            slider.blockSignals(True)
            slider.setValue(int(val * 10))  # slider assumed 0‑1000 scale
            slider.blockSignals(False)
 
        self.edit_win = QtWidgets.QWidget(self.overlay)
        self.edit_win.setFixedSize(1010, 600)
        self.edit_win.setStyleSheet("""
            QWidget {
                /* NEW: PNG background */
                background: url("assets/rack_bg.png") center/cover no-repeat;
                border-radius: 20px;
                color: white;
            }
            QLabel { color:#cfd0d4; font-size:13px; letter-spacing:0.8px; }
        """)
        self.edit_win.move(
            self.width() // 2 - self.edit_win.width() // 2,
            self.height() // 2 - self.edit_win.height() // 2
        )
 
 
        vbox = QtWidgets.QVBoxLayout(self.edit_win)
        vbox.setContentsMargins(34, 38, 34, 34)
        vbox.setSpacing(30)
 
        # ---------- glossy digital title ----------
        self.edit_title = QtWidgets.QLabel(self.current_preset_name)
        self.edit_title.setFixedWidth(398)  # ← adjust this number as needed
        self.edit_title.setAlignment(QtCore.Qt.AlignCenter)
        self.edit_title.setFont(QtGui.QFont(self.digital_family, 36))  # use loaded DS‑Digital
        print("Edit title font:", self.edit_title.font().family())  # Check what font is set
        self.edit_title.update()  # Force refresh

        self.edit_title.setStyleSheet("""
            QLabel {
                color: #8ff;
                background: transparent;
                border: .1px solid #2e2d2d;
                border-radius: 5px;
                padding: 7px 16px;
                letter-spacing: 5px;
            }
        """)
        vbox.addWidget(self.edit_title)
 
 
 
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(30)
        grid.setVerticalSpacing(27)
        vbox.addLayout(grid, 1)
 
        lcd_style = """
            QLabel {
                min-width: 60px;
                background: transparent;               
                border: 0.1px solid #3f7cff;
                border-radius: 5px;
                color: #8ff;
                font-family: 'DS-Digital';
                font-size: 20px;
                padding: 23px 6px;
            }
        """
         # ---------- glass overlay helper --------------------------------
        def add_lcd_glass(lbl):
            glass = QtWidgets.QLabel(lbl.parent())
            glass.setGeometry(lbl.geometry())                # same size / pos
            glass.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        def add_lcd_glass(lbl):
            glass = QtWidgets.QLabel(lbl.parent())
            glass.setGeometry(lbl.geometry())                # same size / pos
            glass.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            glass.setStyleSheet("""
                QLabel {
                    background-color: rgba(100,150,255,100);
                    border-radius:6px;                      /* match LCD */
                }
            """)
            glass.lower()   # keep glass behind the text label
            glass.show()
            return glass
            glass.lower_()   # keep text above glass
            glass.show()
            
        names = [
            "DECAY", "PRE‑DELAY", "SIZE", "DAMPING", "DIFFUSION", "WIDTH",
            "MOD RATE", "MOD DEPTH", "MIX", "LEVEL", "LOW‑CUT", "HIGH‑CUT"
        ]
 
        slider_value_map = {n.upper(): v for n, v in self.SLIDERS}
        slider_widget_map = {n.upper(): s for n, s, _ in self.slider_widgets}
 
        self.knob_controls = {}
 
        for idx, name in enumerate(names):
            col_box = QtWidgets.QVBoxLayout()
            col_box.setSpacing(6)

            dial = PNGDial()
            dial.setRange(0, 100)

            key  = "WET/DRY" if name.upper() == "MIX" else name.upper()
            init = self.preset_values.get(key, 50)
            dial.setValue(int(round(init)))

            # ----- LCD label ---------------------------------------------
            lcd = QtWidgets.QLabel(f"{int(round(init)):02}")
            lcd.setAlignment(QtCore.Qt.AlignCenter)
            lcd.setStyleSheet(lcd_style)
            add_lcd_glass(lcd)          # ← add glossy overlay here
 
            # ----- two‑way binding (knob ↔ slider) ------------------------
            sld = slider_widget_map.get(key)
            print(f"Binding knob to slider for key={key}: slider={sld}, type={type(sld)}")  # <-- add here
            if sld:
                sld.setTracking(True)  # make it talk while you drag
 
                # knob ➜ slider  (dial 0‑100 → slider 0‑1000)
                def knob_to_slider(kv, sl=sld, key=key):
                    sv = kv * 10
                    if sl.value() != sv:
                        sl.blockSignals(True)
                        sl.setValue(sv)
                        sl.blockSignals(False)
                    # Update shared preset values dict
                    self.preset_values[key] = kv
                dial.valueChanged.connect(knob_to_slider)
 
                def slider_to_knob(sv, d=dial, key=key):
                    kv = int(sv / 10)
                    if d.value() != kv:
                        d.blockSignals(True)
                        d.setValue(kv)
                        d.blockSignals(False)
                    # Update shared preset values dict
                    self.preset_values[key] = kv
                sld.valueChanged.connect(slider_to_knob)
                sld.sliderMoved.connect(slider_to_knob)
 
            # keep LCD in sync with knob
            dial.valueChanged.connect(lambda v, l=lcd: l.setText(f"{v:02}"))
 
            # ----- layout -------------------------------------------------
            txt = QtWidgets.QLabel(name)
            txt.setAlignment(QtCore.Qt.AlignCenter)
            txt.setStyleSheet("background:transparent;") 
 
            col_box.addWidget(dial, alignment=QtCore.Qt.AlignCenter)
            col_box.addWidget(lcd,  alignment=QtCore.Qt.AlignCenter)
            col_box.addWidget(txt)
 
            r, c = divmod(idx, 6)
            grid.addLayout(col_box, r, c)
 
            self.knob_controls[name] = dial
 
                # <-- Insert sync here -->
        for name, dial in self.knob_controls.items():
            key = "WET/DRY" if name.upper() == "MIX" else name.upper()
            val = self.preset_values.get(key, 50)
            dial.blockSignals(True)
            dial.setValue(int(round(val)))
            dial.blockSignals(False)
 
        # --------------------------- BUTTON ROW ---------------------------
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(20)
        vbox.addLayout(btn_row)

        def sleek_btn(txt):
            b = QtWidgets.QPushButton(txt)
            b.setFixedSize(140, 35)
            b.setStyleSheet("""
                QPushButton {
                    background-image: none;
                    background: #101010;
                    color: #8fc2ff;
                    border: .5px solid #2D58B5;
                    border-radius: 1px;
                    padding: 6px 14px;
                    font-weight: 500;
                    font-size: 12px;
                    letter-spacing: 3px;
                }
                QPushButton:hover  { background:#3f7cff; color:#fff; }
                QPushButton:pressed{ background:#1a1c20; color:#aaccff; }
                QPushButton:disabled{ background:#111214; color:#555; }
            """)
            return b

        # create buttons
        default_btn = sleek_btn("SHIFT")
        save_btn    = sleek_btn("SAVE")
        cancel_btn  = sleek_btn("CANCEL")
        load_btn    = sleek_btn("LOAD")

        # layout: [DEFAULT] ... SAVE  CANCEL ... [LOAD]
        btn_row.addStretch(0)
        btn_row.addWidget(default_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(10)
        btn_row.addWidget(load_btn)
        btn_row.addStretch(0)

        # example signals
        default_btn.clicked.connect(lambda: print("DEFAULT pressed"))
        load_btn.clicked.connect(lambda: print("LOAD pressed"))

        cancel_btn.clicked.connect(self.overlay.close)
        save_btn.clicked.connect(
            lambda: (print({n: k.value() for n, k in self.knob_controls.items()}),
                     self.overlay.close())
        )

        self.edit_win.show()
        self.edit_win.raise_()
 
    def _start_clock(self): pass
    def _noop(self): pass
 
    class RingDial(QtWidgets.QDial):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
 
            self.setRange(0, 100)
            self.setNotchesVisible(False)
            self.setFixedSize(84, 84)
            self.valueChanged.connect(self.update)
 
            self.setStyleSheet("""
                QDial { background:transparent; }
                QDial::handle {
                    background:#222;
                    border:1px solid #000;
                    width:14px; height:14px;
                    border-radius:7px;
                    margin:-7px;
                }
                QDial::handle:hover { background:#555; }
            """)
 
        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)  # ← Add this line
 
            cx, cy = self.width() / 2, self.height() / 2
            center = QtCore.QPointF(cx, cy)
            radius = min(self.width(), self.height()) / 2 - 4
 
 
 
            # Black face
            grad = QtGui.QRadialGradient(center, radius, center)
            grad.setColorAt(0.0, QtGui.QColor(30, 30, 30))
            grad.setColorAt(1.0, QtGui.QColor(5, 5, 5))
            painter.setBrush(grad)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(center, radius, radius)
 
            # Status ring (270° sweep)
            ratio = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
            sweep_deg = 270 * ratio
            start_deg = 225
            pen = QtGui.QPen(QtGui.QColor(50, 130, 255, 200))
            pen.setWidth(6)
            painter.setPen(pen)
            painter.drawArc(
                QtCore.QRect(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2)),
                int(start_deg * 16),
                int(-sweep_deg * 16)
            )
 
            # LED indicator (moves with ring)
            led_r = 3
            led_angle_deg = start_deg - sweep_deg  # LED angle matches ring progress
            led_angle = math.radians(led_angle_deg)
            led_dist = radius - 8
            led_x = cx + led_dist * math.cos(led_angle)
            led_y = cy - led_dist * math.sin(led_angle)
            led_on = QtGui.QColor(255, 255, 255, 220)  # White LED when on
            led_off = QtGui.QColor(60, 60, 60, 120)     # Dim gray when off
            painter.setBrush(led_on if self.value() else led_off)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawEllipse(QtCore.QPointF(led_x, led_y), led_r, led_r)
 
 
 
    # build interface
    def _compose(self):
        root = QtWidgets.QGridLayout(self.centralWidget())
        root.setContentsMargins(20, 20, 20, 20)
        root.setHorizontalSpacing(30)
 
        label_font = make_font(8, weight=QtGui.QFont.Normal)
 
        def io_slider(label, color, value=60):
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(label)
            lbl.setFont(label_font)
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            bar = AnimatedSlider(QtCore.Qt.Horizontal, color=color)
            bar.setRange(0, 100)
            bar.setValue(value)
            row.addWidget(lbl)
            row.addSpacing(4)
            row.addWidget(bar)
            return row
 
        # -------------- TOP I/O + CLOCK + MENU ---------------------------
        io_row = QtWidgets.QHBoxLayout()
        io_row.setSpacing(14)
        io_row.addLayout(io_slider("L", "#ff3333"))
        io_row.addLayout(io_slider("R", "#ff3333"))
        io_row.addSpacing(8)
        io_row.addWidget(QtWidgets.QLabel("INPUTS"))
        io_row.addStretch(1)

        self.clock = QtWidgets.QLabel()
        self.clock.setFont(make_font(10, weight=QtGui.QFont.Normal))
        io_row.addWidget(self.clock)

        io_row.addStretch(1)
        io_row.addWidget(QtWidgets.QLabel("OUTPUT"))
        io_row.addSpacing(8)
        io_row.addLayout(io_slider("L", "#33ff33"))
        io_row.addLayout(io_slider("R", "#33ff33"))

        # NEW: hamburger button that opens the System‑Menu window
        menu_btn = QtWidgets.QToolButton()
        menu_btn.setText("≡")                       # hamburger glyph
        menu_btn.setFixedSize(46, 34)
        menu_btn.setStyleSheet("""
            QToolButton {
                font-size:24px;
                background:transparent;
                border:none;
                color:white;
            }
            QToolButton:hover { color:#3f7cff; }
        """)
        menu_btn.clicked.connect(self._show_system_menu)   # open full‑screen menu
        io_row.addSpacing(14)
        io_row.addWidget(menu_btn)
        
        # -------------- BYPASS LABEL ------------------------------------        
        self.bypass_lbl = ClickableLabel("BYPASSED")
        self.bypass_lbl.setFont(make_font(10, track=3))
        self.bypass_lbl.setStyleSheet("color:#ff5555;")
        self.bypass_lbl.clicked.connect(self._toggle_bypass)
        bypass_box = QtWidgets.QHBoxLayout()
        bypass_box.setAlignment(QtCore.Qt.AlignLeft)
        bypass_box.addWidget(self.bypass_lbl)
 
        # -------------- TITLES ------------------------------------------
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(4)
        titles.setContentsMargins(0, 60, 0, 0)
        self.main_title = QtWidgets.QLabel(self.current_preset_name)
        self.main_title.setFont(make_font(48, track=0.5))
        titles.addWidget(self.main_title)
 
        rev_type = QtWidgets.QLabel("SPRING + HALL")
        rev_type.setFont(make_font(16, track=1))
        rev_type.setStyleSheet("color:#3f7cff;")
        titles.addWidget(rev_type)
 
        self.pos_lbl = QtWidgets.QLabel(f"Default Preset {self.current_preset_position}")
        self.pos_lbl.setFont(make_font(13, weight=QtGui.QFont.Normal))
        titles.addWidget(self.pos_lbl)
 
        sub = QtWidgets.QLabel("Shimmering highs, bouncy vintage surf")
        sub.setFont(make_font(11, weight=QtGui.QFont.Normal))
        sub.setStyleSheet("color:#bbb")
        titles.addWidget(sub)
        titles.addStretch(1)
 
   # -------------- NAV PANEL ---------------------------------------
        nav_panel = QtWidgets.QFrame()
        nav_panel.setFixedWidth(200)
        nav_panel.setStyleSheet("background:rgba(0,0,0,180); border:none;")
 
        nav_lay = QtWidgets.QVBoxLayout(nav_panel)
        nav_lay.setContentsMargins(10, 20, 10, 20)
        nav_lay.setSpacing(20)
        nav_font = make_font(16, weight=QtGui.QFont.Normal, track=2)
 
        def add_nav_button(text, handler=None):
            b = AnimatedButton(text)
            b.setFont(nav_font)
            if handler:
                b.clicked.connect(handler)
            else:
                b.clicked.connect(lambda _, t=text: print("NAV", t))
            nav_lay.addWidget(b)
            return b
 
        add_nav_button("MODES", self._show_mode_page)
        add_nav_button("PRESETS", self._show_presets)
        add_nav_button("EDIT", self._show_edit_preset)
        add_nav_button("SAVE", self._save_preset)
        add_nav_button("MODULATION", self._show_modulation_page)
        add_nav_button("DYNAMICS")
 
        # TAP button with blinking light ring around the button itself
        self.tap_btn = AnimatedButton("TAP")
        self.tap_btn.setFont(nav_font)
        nav_lay.addWidget(self.tap_btn)
 
        nav_lay.addStretch(1)
 
        # Initialize state for blinking ring
        self._tap_led_on = False
 
        # Base stylesheet for tap button (matches other buttons)
        self._tap_btn_base_style = """
            QPushButton {
                color: white;
                background: rgba(30,30,30,180);
                border: 3px solid transparent;
                padding: 8px 14px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(50,50,50,230);
            }
        """
 
        # Style when ring is ON (blue border)
        self._tap_btn_ring_on_style = """
            QPushButton {
                color: white;
                background: rgba(30,30,30,180);
                border: 3px solid #3f7cff;
                padding: 8px 14px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: rgba(50,50,50,230);
            }
        """
 
        self.tap_btn.setStyleSheet(self._tap_btn_base_style)
 
        self._tap_times = []
 
        def toggle_tap_ring():
            self._tap_led_on = not self._tap_led_on
            if self._tap_led_on:
                self.tap_btn.setStyleSheet(self._tap_btn_ring_on_style)
            else:
                self.tap_btn.setStyleSheet(self._tap_btn_base_style)
 
        def on_tap():
            now = QtCore.QTime.currentTime().msecsSinceStartOfDay()
            self._tap_times.append(now)
            if len(self._tap_times) > 4:
                self._tap_times.pop(0)
 
            if len(self._tap_times) >= 2:
                intervals = [
                    self._tap_times[i] - self._tap_times[i - 1] for i in range(1, len(self._tap_times))
                ]
                avg_interval = sum(intervals) / len(intervals)
                bpm = 60000 / avg_interval if avg_interval > 0 else 0
 
                interval_ms = int(avg_interval / 2)  # blink twice per beat
 
                if hasattr(self, "_tap_blink_timer") and self._tap_blink_timer.isActive():
                    self._tap_blink_timer.setInterval(interval_ms)
                else:
                    self._tap_blink_timer = QtCore.QTimer()
                    self._tap_blink_timer.timeout.connect(toggle_tap_ring)
                    self._tap_blink_timer.start(interval_ms)
            else:
                # Less than 2 taps — flash briefly
                if hasattr(self, "_tap_blink_timer"):
                    self._tap_blink_timer.stop()
                self.tap_btn.setStyleSheet(self._tap_btn_ring_on_style)
                QtCore.QTimer.singleShot(300, lambda: self.tap_btn.setStyleSheet(self._tap_btn_base_style))
 
        self.tap_btn.clicked.connect(on_tap)
 
 
        # -------------- SLIDER BAR --------------------------------------
        bottom = QtWidgets.QWidget()
        bottom.setStyleSheet("background:rgba(0,0,0,140);")
        bot_lay = QtWidgets.QHBoxLayout(bottom)
        bot_lay.setContentsMargins(20, 12, 20, 12)
        bot_lay.setSpacing(30)
        slide_font = make_font(10, weight=QtGui.QFont.Normal)
 
        for name, default in self.SLIDERS:
                col = QtWidgets.QVBoxLayout()
                col.setSpacing(6)
 
    # numeric label under the slider
                lbl_val = QtWidgets.QLabel(f"{default}")
                lbl_val.setFont(slide_font)
                lbl_val.setAlignment(QtCore.Qt.AlignCenter)
 
    # the slider itself
                sld = AnimatedSlider(QtCore.Qt.Horizontal)
                sld.setRange(0, 1000)
                sld.setValue(int(default * 10))
 
    # --- hook up the slider ---
                sld.valueChanged.connect(lambda v, l=lbl_val: l.setText(f"{v / 10:.1f}"))
                sld.valueChanged.connect(lambda v, n=name.upper(): sync_controls(n, v, "slider"))
 
    # --- register in the global maps AFTER sld exists ---
                slider_widget_map[name.upper()] = sld
                slider_label_map[name.upper()]  = lbl_val    # NEW map for quick label updates
 
    # build column
                lbl_name = QtWidgets.QLabel(name)
                lbl_name.setFont(slide_font)
                lbl_name.setAlignment(QtCore.Qt.AlignCenter)
 
                col.addWidget(lbl_val)
                col.addWidget(sld)
                col.addSpacing(4)
                col.addWidget(lbl_name)
                bot_lay.addLayout(col)
 
                self.slider_widgets.append((name, sld, lbl_val))
 
        # -------------- GRID PLACEMENT -----------------------------------
        root.addLayout(io_row,   0, 0, 1, 3)
        root.addLayout(bypass_box, 1, 0, 1, 3)
        root.addLayout(titles,   2, 0, 1, 2)
        root.addWidget(nav_panel, 2, 2, 3, 1)
        root.addWidget(bottom,   4, 0, 1, 3)
        root.setColumnStretch(1, 1)
        root.setRowStretch(3, 1)
 
    # utilities / preset logic
    def _start_clock(self):
        timer = QtCore.QTimer(self)
        timer.timeout.connect(lambda: self.clock.setText(datetime.now().strftime("%H:%M")))
        timer.start(1000)
        self.clock.setText(datetime.now().strftime("%H:%M"))
 
    def _toggle_bypass(self):
        self._is_bypassed = not self._is_bypassed
        self.bypass_lbl.setText("BYPASSED" if self._is_bypassed else "ACTIVE")
        self.bypass_lbl.setStyleSheet("color:#ff5555;" if self._is_bypassed else "color:#55ff55;")
        
    def _refresh_edit_title(self):
        """Update the digital title in the Edit window (if it’s open)."""
        if hasattr(self, "edit_title"):
            self.edit_title.setText(self.current_preset_name) 
                
 
    def _next_pos(self):
        rows, cols = range(1, 5), "ABCDEF"
        used = {p["position"] for p in self.presets.values()}
        for r in rows:
            for c in cols:
                pos = f"{r}{c}"
                if pos not in used:
                    return pos
        return "??"
 
    def _save_preset(self):
        suggested = self._next_pos()
        dlg = SavePresetDialog(self.current_preset_name, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        name = dlg.get_values().strip()
        if not name:
            DarkMessageDialog("Invalid Input",
                              "Preset name must be entered.", self).exec_()
            return
        if name in self.presets:
            DarkMessageDialog("Duplicate Name",
                              f"A preset named '{name}' already exists.", self).exec_()
            return

        # collect slider values (0‑100 scale)
        vals = {n: s.value() / 10 for n, s, _ in self.slider_widgets}
        self.presets[name] = {
            "position": suggested,
            "values": vals,
            "modulation": {
                "mod": mod_value_map.copy(),
                "bic": bic_value_map.copy(),
                "ech": ech_value_map.copy()
            }
        }
                # ---------- write presets to disk ----------
        try:
            with open(self.preset_file, "w") as f:
                json.dump(self.presets, f, indent=2)
            print("Presets written to", self.preset_file)
        except Exception as e:
            print("Preset‑file write error:", e)

        # ---- update titles everywhere ----
        self.current_preset_name, self.current_preset_position = name, suggested
        self.main_title.setText(name)          # main‑screen heading
        self._refresh_edit_title()             # glossy digital heading in Edit window
        self.pos_lbl.setText(f"User Preset {suggested}")

        SuccessMessageDialog(
            f"Preset '{name}' saved at {suggested}", self
        ).exec_()
 
    def _load_preset(self, name: str):
        if name not in self.presets:
            return
        data = self.presets[name]
        for n, sld, lbl in self.slider_widgets:
            sld.setValue(int(data["values"].get(n, 0) * 10))

        modulation = data.get("modulation", {})
        mod_vals = modulation.get("mod", {})
        bic_vals = modulation.get("bic", {})
        ech_vals = modulation.get("ech", {})

        for k, v in mod_vals.items():
            mod_value_map[k] = v
        for k, v in bic_vals.items():
            bic_value_map[k] = v
        for k, v in ech_vals.items():
            ech_value_map[k] = v

        if hasattr(self, "mod_knobs"):
            for name, knob in self.mod_knobs.items():
                knob.setValue(int(mod_value_map.get(name, 0)))
        if hasattr(self, "bic_knobs"):
            for name, knob in self.bic_knobs.items():
                knob.setValue(int(bic_value_map.get(name, 0)))
        if hasattr(self, "ech_knobs"):
            for name, knob in self.ech_knobs.items():
                knob.setValue(int(ech_value_map.get(name, 0)))

        self.current_preset_name, self.current_preset_position = name, data["position"]
        self.main_title.setText(name)
        self.pos_lbl.setText(f"User Preset {data['position']}")
        self._refresh_edit_title()                     # keep Edit window in sync

    def _show_presets(self):
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
        self.overlay.show()
        self.overlay.raise_()

        self.presets_win = PresetsWindow(self.presets, self.overlay)
        self.presets_win.preset_selected.connect(self._load_preset)
    
        # Explicitly connect closeEvent of presets_win to close overlay
        def on_presets_close(event):
            self.overlay.close()
            event.accept()
    
        self.presets_win.closeEvent = on_presets_close

        cx = self.width() // 2 - self.presets_win.width() // 2
        cy = self.height() // 2 - self.presets_win.height() // 2
        self.presets_win.move(cx, cy)
        self.presets_win.show()
        self.presets_win.raise_()
        
    def load_mod_presets(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "mod_presets.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.bic_presets = json.load(f).get("bic", {})
                    self.mod_presets = json.load(f).get("mod", {})
                    self.ech_presets = json.load(f).get("ech", {})
        except Exception as e:
            print("Error loading mod presets:", e)

    def save_mod_presets(self):
        try:
            path = os.path.join(os.path.dirname(__file__), "mod_presets.json")
            data = {
                "bic": self.bic_presets,
                "mod": self.mod_presets,
                "ech": self.ech_presets
            }
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Error saving mod presets:", e)
            
    def _show_dynamics_page(self):
        # ---- dim background ----
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
        self.overlay.show()
        self.overlay.raise_()

        # ---- modulation window ----
        self.mod_win = QtWidgets.QWidget(self.overlay)
        self.mod_win.setFixedSize(1024, 600)
        self.mod_win.setStyleSheet("""
            QWidget {
                background: url("assets/dynamics_bg.png") no-repeat center center;
                background-size: cover;
                border-radius: 12px;
            }
        """)
        self.mod_win.destroyed.connect(self.overlay.close)

        # centre window
        cx = self.width()  // 2 - self.mod_win.width()  // 2
        cy = self.height() // 2 - self.mod_win.height() // 2
        self.mod_win.move(cx, cy)

        # ---------- glass overlay helper --------------------------------
        def add_lcd_glass(lbl):
            glass = QtWidgets.QLabel(lbl.parent())
            glass.setGeometry(lbl.geometry())
            glass.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            glass.setStyleSheet("""
                QLabel {
                    background-color: rgba(100,150,255,100);
                    border-radius:6px;
                }
            """)
            glass.lower()
            glass.show()
            return glass

        # ---------- helper to build a knob with a custom PNG ------------
        def custom_knob(png_path: str, offset: int = 0, label: str = "", x: int = 0, y: int = 0):
            kb = PNGDial(self.mod_win,
                         img_path=png_path,
                         angle_offset=offset)
            kb.setFixedSize(80, 80)
            kb.setRange(0, 100)
            kb.setValue(50)
            kb.move(x, y)
            kb.show()

            # value label under knob
            val_lbl = QtWidgets.QLabel("50", self.mod_win)
            val_lbl.setAlignment(QtCore.Qt.AlignCenter)
            val_lbl.setStyleSheet("""
                QLabel {
                    background: transparent;
                    color: #ffffff;
                    font-family: 'Calibri';
                    font-size: 14px;
                }
            """)
            val_lbl.setFixedSize(60, 20)
            val_lbl.move(x + 10, y + 84)
            val_lbl.show()

            # label above knob
            txt_lbl = QtWidgets.QLabel(label.upper(), self.mod_win)
            txt_lbl.setAlignment(QtCore.Qt.AlignCenter)
            txt_lbl.setStyleSheet("color: #ffffff; background: transparent; font-size: 10px; letter-spacing: 1px;")
            txt_lbl.setFixedWidth(80)
            txt_lbl.move(x, y - 24)  # moved 10px higher
            txt_lbl.show()

            def update_label(val):
                val_lbl.setText(f"{val:02}")
            kb.valueChanged.connect(update_label)

            return kb
        # ----------------------------------------------------------------

        # ------- flat button factory ------------------------------------
        def _flat_btn(txt: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(txt, self.mod_win)   # parent = mod_win
            b.setFixedSize(95, 26)
            b.setStyleSheet("""
                QPushButton {
                    background: #101010;
                    color: #8fc2ff;
                    border: .5px solid #2D58B5;
                    border-radius: 1px;
                    font-size: 12px;
                    font-weight: 500;
                    letter-spacing: 2px;
                }
                QPushButton:hover {
                    background: #1e1e1e;
                }
                QPushButton:pressed {
                    background: #3f7cff;
                    color: #fff;
                    border-color: #3f7cff;
                }
            """)
            return b

        # ------- toggle button factory ----------------------------------
        def _toggle_btn(txt: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(txt, self.mod_win)
            b.setCheckable(True)
            b.setFixedSize(192, 26)  # resized to match save buttons
            b.setStyleSheet("""
                QPushButton {
                    background: #000000;
                    color: #505050;
                    border: .5px solid #505050;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: 500;
                    letter-spacing: 3px;
                }
                QPushButton:hover {
                    background: #1a1a1a;
                }
                QPushButton:pressed {
                    background: #000000;
                    color: #77F000;
                    border-color: #3f7cff;
                }
                QPushButton:checked {
                    background: #000000;
                    color: #ffffff;
                    border-color: #ffffff;
                }
            """)
            def update_text(checked):
                b.setText("ACTIVE" if checked else "BYPASSED")
            b.toggled.connect(update_text)
            b.setChecked(True)  # Default ON state
            return b

        # ------- screen factory -----------------------------------------
        def _screen() -> QtWidgets.QLineEdit:
            le = QtWidgets.QLineEdit(self.mod_win)         # parent = mod_win
            le.setFixedSize(200, 38)
            le.setAlignment(QtCore.Qt.AlignCenter)
            le.setStyleSheet("""
                QLineEdit {
                    background: rgba(0,0,20,140);
                    border: .5px solid #555;
                    border-radius: 4px;
                    color: #8fc2ff;
                    font-size: 14px;
                }
            """)
            return le



        # === HELPER TO GET CURRENT KNOB VALUES PER UNIT ===
        def get_bic_knob_values():
            values = {}
            for lbl, knob in bic_knobs.items():
                values[lbl] = knob.value()
            return values

        def set_bic_knob_values(values):
            for lbl, val in values.items():
                if lbl in bic_knobs:
                    bic_knobs[lbl].setValue(val)

        def get_mod_knob_values():
            values = {}
            for lbl, knob in mod_knobs.items():
                values[lbl] = knob.value()
            return values

        def set_mod_knob_values(values):
            for lbl, val in values.items():
                if lbl in mod_knobs:
                    mod_knobs[lbl].setValue(val)

        def get_ech_knob_values():
            values = {}
            for lbl, knob in ech_knobs.items():
                values[lbl] = knob.value()
            return values

        def set_ech_knob_values(values):
            for lbl, val in values.items():
                if lbl in ech_knobs:
                    ech_knobs[lbl].setValue(val)

        # === PRESET SELECTION DIALOG ===
        def show_preset_selector(presets_dict, set_knobs_func, current_preset_attr, screen_label):
            preset_names = list(presets_dict.keys())
            if not preset_names:
                dlg = CustomMessageDialog("No presets", "No presets saved yet.", parent=self.mod_win)
                dlg.label.setStyleSheet("background: transparent")  # black bg with some padding
                dlg.exec_()
                return

            dialog = QtWidgets.QDialog(self.mod_win)
            dialog.setWindowTitle("Select Preset")
            dialog.setFixedSize(300, 400)
            dialog.setStyleSheet("""
                QDialog { background:transparent; color:#8fc2ff; border-radius:12px; }
                QListWidget { background:transparent; border-radius:8px; color:#8fc2ff; font-size:14px; }
                QPushButton {
                    background:#3f7cff; border:none; border-radius:6px;
                    padding:10px 24px; color:white; font-weight:bold; font-size:14px;
                }
                QPushButton:hover { background:#5591ff; }
                QPushButton:pressed { background:#2c62cc; }
            """)

            layout = QtWidgets.QVBoxLayout(dialog)

            layout.addWidget(QtWidgets.QLabel("Select a preset:"))
            label = layout.itemAt(layout.count() - 1).widget()
            label.setStyleSheet("background: transparent; padding: 4px 8px;")

            list_widget = QtWidgets.QListWidget(dialog)
            list_widget.addItems(preset_names)
            layout.addWidget(list_widget)

            btn_box = QtWidgets.QHBoxLayout()
            ok_btn = QtWidgets.QPushButton("OK", dialog)
            cancel_btn = QtWidgets.QPushButton("Cancel", dialog)
            btn_box.addWidget(ok_btn)
            btn_box.addWidget(cancel_btn)
            layout.addLayout(btn_box)

            def on_ok():
                selected_items = list_widget.selectedItems()
                if selected_items:
                    preset_name = selected_items[0].text()
                    set_knobs_func(presets_dict[preset_name])
                    setattr(self, current_preset_attr, preset_name)
                    screen_label.setText(preset_name)
                    dialog.accept()
                else:
                    dlg = CustomMessageDialog("Select a preset", "Please select a preset.", parent=dialog)
                    dlg.exec_()

            ok_btn.clicked.connect(on_ok)
            cancel_btn.clicked.connect(dialog.reject)

            dialog.exec_()

        # === SAVE PRESET PROMPT ===
        def save_preset(presets_dict, get_knobs_func, current_preset_attr, screen_label):
            dialog = SavePresetDialog(getattr(self, current_preset_attr) or "", parent=self.mod_win)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                name = dialog.get_values()
                if not name:
                    return
                if name in presets_dict:
                    overwrite_dialog = QtWidgets.QMessageBox(self.mod_win)
                    overwrite_dialog.setWindowTitle("Overwrite?")
                    overwrite_dialog.setText(f"Preset '{name}' exists. Overwrite?")
                    overwrite_dialog.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                    overwrite_dialog.setStyleSheet("""QMessageBox { background:#121212; color:white; }""")
                    if overwrite_dialog.exec_() == QtWidgets.QMessageBox.No:
                        return
                presets_dict[name] = get_knobs_func()
                setattr(self, current_preset_attr, name)
                screen_label.setText(name)

                success = SuccessMessageDialog(f"Preset '{name}' saved.", parent=self.mod_win)
                success.setStyleSheet("background: transparent; padding: 4px 8px;")  # black bg with some padding
                success.exec_()
                self.save_mod_presets()  # persist changes


        # === UPDATE PRESET ===
        def update_preset(presets_dict, get_knobs_func, current_preset_attr, screen_label):
            name = getattr(self, current_preset_attr)
            if not name:
                QtWidgets.QMessageBox.warning(self.mod_win, "No preset selected", "Please select a preset first.")
                return
            presets_dict[name] = get_knobs_func()
            screen_label.setText(name)
            self.save_mod_presets()  # persist changes

        # === KNOBS DICTIONARIES TO LINK LABELS TO KNOBS ===
        bic_knobs = {
            "Rate": custom_knob("assets/knob_black.png", +90, label="Rate", x=539, y=50),
            "Depth": custom_knob("assets/knob_black.png", +90, label="Depth", x=410, y=50),
            "Tone": custom_knob("assets/knob_black.png", +90, label="Tone", x=279, y=50),
            "Mix": custom_knob("assets/knob_black.png", +90, label="Mix", x=152, y=50),
        }

        for name, knob in bic_knobs.items():
            knob.setValue(int(bic_value_map.get(name, 0)))
            knob.valueChanged.connect(lambda val, n=name: bic_value_map.update({n: val}))
            
        mod_knobs = {
            "Speed": custom_knob("assets/knob_gunmetal.png", +240, label="Speed", x=814, y=247),
            "Shape": custom_knob("assets/knob_gunmetal.png", +240, label="Shape", x=685, y=247),
            "Phase": custom_knob("assets/knob_gunmetal.png", +240, label="Phase", x=267, y=247),
            "Spread": custom_knob("assets/knob_gunmetal.png", +240, label="Spread", x=138, y=247),
        }

        for name, knob in mod_knobs.items():
            knob.setValue(int(mod_value_map.get(name, 0)))
            knob.valueChanged.connect(lambda val, n=name: mod_value_map.update({n: val}))
            
        ech_knobs = {
            "Time": custom_knob("assets/knob_gold.png", +145, label="Time", x=83, y=430),
            "FB": custom_knob("assets/knob_gold.png", +145, label="FB", x=181, y=430),
            "Tone": custom_knob("assets/knob_gold.png", +145, label="Tone", x=279, y=430),
            "Mod": custom_knob("assets/knob_gold.png", +145, label="Mod", x=377, y=430),
            "Mix": custom_knob("assets/knob_gold.png", +145, label="Mix", x=475, y=430),
            "Level": custom_knob("assets/knob_gold.png", +145, label="Level", x=573, y=430),
        }

        for name, knob in ech_knobs.items():
            knob.setValue(int(ech_value_map.get(name, 0)))
            knob.valueChanged.connect(lambda val, n=name: ech_value_map.update({n: val}))
            
        self.bic_knobs = bic_knobs
        self.mod_knobs = mod_knobs
        self.ech_knobs = ech_knobs    
            

        # -------- ABSOLUTE‑POSITION BLUE BUTTONS ------------------------
        # BiCorus buttons
       # bic_save    = _flat_btn("SAVE")      ; bic_save.move(697, 104)
       # bic_presets = _flat_btn("PRESETS")  ; bic_presets.move(794, 104)
        bic_bypass  = _toggle_btn("ACTIVE") ; bic_bypass.move(697, 113)  # under SAVE
       # bic_update  = _flat_btn("UPDATE")    ; bic_update.move(794, 134)  # right of bypass

        # ModuLator buttons
       # mod_save    = _flat_btn("SAVE")      ; mod_save.move(417, 296)
       # mod_presets = _flat_btn("PRESETS")  ; mod_presets.move(514, 296)
        mod_bypass  = _toggle_btn("ACTIVE") ; mod_bypass.move(417, 305)  # under SAVE
       # mod_update  = _flat_btn("UPDATE")    ; mod_update.move(514, 324)  # right of bypass

        # EchoSphere buttons
       # ech_save    = _flat_btn("SAVE")      ; ech_save.move(744, 474)
       # ech_presets = _flat_btn("PRESETS")  ; ech_presets.move(842, 474)
        ech_bypass  = _toggle_btn("ACTIVE") ; ech_bypass.move(744, 489)  # under SAVE
       # ech_update  = _flat_btn("UPDATE")    ; ech_update.move(842, 502)  # right of bypass

        # -------- ABSOLUTE‑POSITION SCREENS -----------------------------
        bic_screen = _screen() ; bic_screen.move(692,  51)
        mod_screen = _screen() ; mod_screen.move(413, 241)
        ech_screen = _screen() ; ech_screen.move(739, 424)

        # Set initial screen text to empty (no preset selected)
        bic_screen.setText("T r i C h o r u s")
        mod_screen.setText("S p a c e   I m a g e r")
        ech_screen.setText("8 0 s   T a p e   D e l a y")

        # Connect buttons to their functions:
       # bic_save.clicked.connect(lambda: save_preset(self.bic_presets, get_bic_knob_values, "bic_current_preset", bic_screen))
       # bic_presets.clicked.connect(lambda: show_preset_selector(self.bic_presets, set_bic_knob_values, "bic_current_preset", bic_screen))
       # bic_update.clicked.connect(lambda: update_preset(self.bic_presets, get_bic_knob_values, "bic_current_preset", bic_screen))

       # mod_save.clicked.connect(lambda: save_preset(self.mod_presets, get_mod_knob_values, "mod_current_preset", mod_screen))
       # mod_presets.clicked.connect(lambda: show_preset_selector(self.mod_presets, set_mod_knob_values, "mod_current_preset", mod_screen))
       # mod_update.clicked.connect(lambda: update_preset(self.mod_presets, get_mod_knob_values, "mod_current_preset", mod_screen))

       # ech_save.clicked.connect(lambda: save_preset(self.ech_presets, get_ech_knob_values, "ech_current_preset", ech_screen))
       # ech_presets.clicked.connect(lambda: show_preset_selector(self.ech_presets, set_ech_knob_values, "ech_current_preset", ech_screen))
       # ech_update.clicked.connect(lambda: update_preset(self.ech_presets, get_ech_knob_values, "ech_current_preset", ech_screen))

        # bring overlays to front
        for w in (
       #     bic_save, bic_presets, bic_bypass, bic_update,
       #     mod_save, mod_presets, mod_bypass, mod_update,
       #     ech_save, ech_presets, ech_bypass, ech_update,
            bic_screen, mod_screen, ech_screen
        ):
            w.raise_()

        close_btn = QtWidgets.QPushButton("CLOSE", self.mod_win)
        close_btn.setFixedSize(140, 35)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #101010;
                color: #8fc2ff;
                border: .5px solid #2D58B5;
                border-radius: 1px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 3px;
            }
            QPushButton:hover {
                background: #3f7cff;
                color: #fff;
            }
            QPushButton:pressed {
                background: #1a1c20;
                color: #aaccff;
            }
        """)
        # Position at bottom center:
        close_btn.move(self.mod_win.width() // 2 - close_btn.width() // 2, self.mod_win.height() - 52)
        def on_close():
            if self.bic_current_preset:
                self.bic_presets[self.bic_current_preset] = get_bic_knob_values()
                self.save_bic_presets()
            if self.mod_current_preset:
                self.mod_presets[self.mod_current_preset] = get_mod_knob_values()
                self.save_mod_presets()
            if self.ech_current_preset:
                self.ech_presets[self.ech_current_preset] = get_ech_knob_values()
                self.save_ech_presets()
            self.overlay.close()

        close_btn.clicked.connect(on_close)
        self.mod_win.show()

    def _show_routing_page(self):
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
        self.overlay.show()
        self.overlay.raise_()

        self.route_win = QtWidgets.QWidget(self.overlay)
        self.route_win.setFixedSize(1024, 600)
        self.route_win.setStyleSheet("background-color: #0f0f0f; border-radius: 12px;")
        self.route_win.move(self.width()//2 - 512, self.height()//2 - 300)

        close_btn = QtWidgets.QPushButton("CLOSE", self.route_win)
        close_btn.setFixedSize(140, 35)
        close_btn.move(442, 540)
        close_btn.clicked.connect(self.overlay.close)
        self.route_win.show()  

    def _show_scenes_page(self):
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
        self.overlay.show()
        self.overlay.raise_()

        self.scenes_win = QtWidgets.QWidget(self.overlay)
        self.scenes_win.setFixedSize(1024, 600)
        self.scenes_win.setStyleSheet("""
            QWidget {
                background-color: #141414;
                border-radius: 12px;
            }
        """)
        self.scenes_win.move(
            self.width() // 2 - self.scenes_win.width() // 2,
            self.height() // 2 - self.scenes_win.height() // 2
        )

        # Title Label
        title = QtWidgets.QLabel("SCENES", self.scenes_win)
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setFont(QtGui.QFont("Segoe UI", 24, QtGui.QFont.Bold))
        title.setStyleSheet("color: #8fc2ff; letter-spacing: 3px;")
        title.setGeometry(0, 30, 1024, 60)

        # Close Button
        close_btn = QtWidgets.QPushButton("CLOSE", self.scenes_win)
        close_btn.setFixedSize(140, 35)
        close_btn.move(442, 540)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #101010;
                color: #8fc2ff;
                border: .5px solid #2D58B5;
                border-radius: 1px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 3px;
            }
            QPushButton:hover {
                background: #3f7cff;
                color: #fff;
            }
            QPushButton:pressed {
                background: #1a1c20;
                color: #aaccff;
            }
        """)
        close_btn.clicked.connect(self.overlay.close)

        self.scenes_win.show()        
        
    # ------------------------------------------------------------------
    # full‑screen System‑Menu (1024×600) with dim overlay
    # ------------------------------------------------------------------
    def _show_system_menu(self):
        # ---- dim background ----
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
        self.overlay.show()
        self.overlay.raise_()

        # ---- system‑menu window ----
        self.menu_win = QtWidgets.QWidget(self.overlay)
        self.menu_win.setFixedSize(1024, 600)
        self.menu_win.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #202226, stop:1 #0f1012);
                color: white;
                border-radius: 12px;
            }
            QLabel { font-size:13px; color:#cfd0d4; }
        """)

        self.menu_win.destroyed.connect(self.overlay.close)   # ← add this

        # center on screen
        cx = self.width()  // 2 - self.menu_win.width()  // 2
        cy = self.height() // 2 - self.menu_win.height() // 2
        self.menu_win.move(cx, cy)

        # ---- layout ----
        vbox = QtWidgets.QVBoxLayout(self.menu_win)
        vbox.setContentsMargins(32, 32, 32, 32)
        vbox.setSpacing(28)

        title = QtWidgets.QLabel("SYSTEM MENU")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setFont(QtGui.QFont(self.digital_family, 34))
        title.setStyleSheet("color:#8ff; letter-spacing:3px;")
        vbox.addWidget(title)

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(40)
        grid.setVerticalSpacing(30)
        vbox.addLayout(grid, 1)

        # menu items typical of a pro reverb pedal
        items = [
            "Routing", "Global EQ", "Expression / CV", "MIDI Settings",
            "Footswitch Functions", "Tap‑Tempo Options", "Trails / Spillover",
            "Kill‑Dry", "Firmware Info", "System Settings"
        ]

        def menu_btn(text):
            b = QtWidgets.QPushButton(text)
            b.setFixedSize(260, 46)
            b.setStyleSheet("""
                QPushButton {
                    background:#121316; color:#8fc2ff;
                    border:1px solid #3f7cff; border-radius:6px;
                    font-size:14px; letter-spacing:1px;
                }
                QPushButton:hover  { background:#3f7cff; color:#fff; }
                QPushButton:pressed{ background:#1a1c20; color:#aaccff; }
            """)
            # placeholder: print which menu item clicked
            b.clicked.connect(lambda _, t=text: print("MENU:", t))
            return b

        # arrange buttons in two columns
        for idx, txt in enumerate(items):
            r, c = divmod(idx, 2)
            grid.addWidget(menu_btn(txt), r, c)

        # ---- CLOSE button ----
        close_btn = QtWidgets.QPushButton("CLOSE")
        close_btn.setFixedSize(160, 38)
        close_btn.setStyleSheet("""
            QPushButton {
                background:#000; color:#ff5555;
                border:1px solid #ff5555; border-radius:4px;
                font-size:13px; letter-spacing:2px;
            }
            QPushButton:hover  { background:#ff5555; color:#fff; }
            QPushButton:pressed{ background:#661111; }
        """)
        close_btn.clicked.connect(self.overlay.close)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(close_btn)
        hbox.addStretch(1)
        vbox.addLayout(hbox)

        self.menu_win.show()
        self.menu_win.raise_()  
        
    # ------------------------------------------------------------------
    # full‑screen Modulation (1024×600) with dim overlay
    # ------------------------------------------------------------------        
    def _show_modulation_page(self):
        # ---- dim background ----
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
        self.overlay.show()
        self.overlay.raise_()

        # ---- modulation window ----
        self.mod_win = QtWidgets.QWidget(self.overlay)
        self.mod_win.setFixedSize(1024, 600)
        self.mod_win.setStyleSheet("""
            QWidget {
                background: url("assets/modulation_bg.png") no-repeat center center;
                background-size: cover;
                border-radius: 12px;
            }
        """)
        self.mod_win.destroyed.connect(self.overlay.close)

        # centre window
        cx = self.width()  // 2 - self.mod_win.width()  // 2
        cy = self.height() // 2 - self.mod_win.height() // 2
        self.mod_win.move(cx, cy)

        # ---------- glass overlay helper --------------------------------
        def add_lcd_glass(lbl):
            glass = QtWidgets.QLabel(lbl.parent())
            glass.setGeometry(lbl.geometry())
            glass.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            glass.setStyleSheet("""
                QLabel {
                    background-color: rgba(100,150,255,100);
                    border-radius:6px;
                }
            """)
            glass.lower()
            glass.show()
            return glass

        # ---------- helper to build a knob with a custom PNG ------------
        def custom_knob(png_path: str, offset: int = 0, label: str = "", x: int = 0, y: int = 0):
            kb = PNGDial(self.mod_win,
                         img_path=png_path,
                         angle_offset=offset)
            kb.setFixedSize(80, 80)
            kb.setRange(0, 100)
            kb.setValue(50)
            kb.move(x, y)
            kb.show()

            # value label under knob
            val_lbl = QtWidgets.QLabel("50", self.mod_win)
            val_lbl.setAlignment(QtCore.Qt.AlignCenter)
            val_lbl.setStyleSheet("""
                QLabel {
                    background: transparent;
                    color: #ffffff;
                    font-family: 'Calibri';
                    font-size: 14px;
                }
            """)
            val_lbl.setFixedSize(60, 20)
            val_lbl.move(x + 10, y + 84)
            val_lbl.show()

            # label above knob
            txt_lbl = QtWidgets.QLabel(label.upper(), self.mod_win)
            txt_lbl.setAlignment(QtCore.Qt.AlignCenter)
            txt_lbl.setStyleSheet("color: #ffffff; background: transparent; font-size: 10px; letter-spacing: 1px;")
            txt_lbl.setFixedWidth(80)
            txt_lbl.move(x, y - 24)  # moved 10px higher
            txt_lbl.show()

            def update_label(val):
                val_lbl.setText(f"{val:02}")
            kb.valueChanged.connect(update_label)

            return kb
        # ----------------------------------------------------------------

        # ------- flat button factory ------------------------------------
        def _flat_btn(txt: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(txt, self.mod_win)   # parent = mod_win
            b.setFixedSize(95, 26)
            b.setStyleSheet("""
                QPushButton {
                    background: #101010;
                    color: #8fc2ff;
                    border: .5px solid #2D58B5;
                    border-radius: 1px;
                    font-size: 12px;
                    font-weight: 500;
                    letter-spacing: 2px;
                }
                QPushButton:hover {
                    background: #1e1e1e;
                }
                QPushButton:pressed {
                    background: #3f7cff;
                    color: #fff;
                    border-color: #3f7cff;
                }
            """)
            return b

        # ------- toggle button factory ----------------------------------
        def _toggle_btn(txt: str) -> QtWidgets.QPushButton:
            b = QtWidgets.QPushButton(txt, self.mod_win)
            b.setCheckable(True)
            b.setFixedSize(192, 26)  # resized to match save buttons
            b.setStyleSheet("""
                QPushButton {
                    background: #000000;
                    color: #505050;
                    border: .5px solid #505050;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: 500;
                    letter-spacing: 3px;
                }
                QPushButton:hover {
                    background: #1a1a1a;
                }
                QPushButton:pressed {
                    background: #000000;
                    color: #77F000;
                    border-color: #3f7cff;
                }
                QPushButton:checked {
                    background: #000000;
                    color: #ffffff;
                    border-color: #ffffff;
                }
            """)
            def update_text(checked):
                b.setText("ACTIVE" if checked else "BYPASSED")
            b.toggled.connect(update_text)
            b.setChecked(True)  # Default ON state
            return b

        # ------- screen factory -----------------------------------------
        def _screen() -> QtWidgets.QLineEdit:
            le = QtWidgets.QLineEdit(self.mod_win)         # parent = mod_win
            le.setFixedSize(200, 38)
            le.setAlignment(QtCore.Qt.AlignCenter)
            le.setStyleSheet("""
                QLineEdit {
                    background: rgba(0,0,20,140);
                    border: .5px solid #555;
                    border-radius: 4px;
                    color: #8fc2ff;
                    font-size: 14px;
                }
            """)
            return le



        # === HELPER TO GET CURRENT KNOB VALUES PER UNIT ===
        def get_bic_knob_values():
            values = {}
            for lbl, knob in bic_knobs.items():
                values[lbl] = knob.value()
            return values

        def set_bic_knob_values(values):
            for lbl, val in values.items():
                if lbl in bic_knobs:
                    bic_knobs[lbl].setValue(val)

        def get_mod_knob_values():
            values = {}
            for lbl, knob in mod_knobs.items():
                values[lbl] = knob.value()
            return values

        def set_mod_knob_values(values):
            for lbl, val in values.items():
                if lbl in mod_knobs:
                    mod_knobs[lbl].setValue(val)

        def get_ech_knob_values():
            values = {}
            for lbl, knob in ech_knobs.items():
                values[lbl] = knob.value()
            return values

        def set_ech_knob_values(values):
            for lbl, val in values.items():
                if lbl in ech_knobs:
                    ech_knobs[lbl].setValue(val)

        # === PRESET SELECTION DIALOG ===
        def show_preset_selector(presets_dict, set_knobs_func, current_preset_attr, screen_label):
            preset_names = list(presets_dict.keys())
            if not preset_names:
                dlg = CustomMessageDialog("No presets", "No presets saved yet.", parent=self.mod_win)
                dlg.label.setStyleSheet("background: transparent")  # black bg with some padding
                dlg.exec_()
                return

            dialog = QtWidgets.QDialog(self.mod_win)
            dialog.setWindowTitle("Select Preset")
            dialog.setFixedSize(300, 400)
            dialog.setStyleSheet("""
                QDialog { background:transparent; color:#8fc2ff; border-radius:12px; }
                QListWidget { background:transparent; border-radius:8px; color:#8fc2ff; font-size:14px; }
                QPushButton {
                    background:#3f7cff; border:none; border-radius:6px;
                    padding:10px 24px; color:white; font-weight:bold; font-size:14px;
                }
                QPushButton:hover { background:#5591ff; }
                QPushButton:pressed { background:#2c62cc; }
            """)

            layout = QtWidgets.QVBoxLayout(dialog)

            layout.addWidget(QtWidgets.QLabel("Select a preset:"))
            label = layout.itemAt(layout.count() - 1).widget()
            label.setStyleSheet("background: transparent; padding: 4px 8px;")

            list_widget = QtWidgets.QListWidget(dialog)
            list_widget.addItems(preset_names)
            layout.addWidget(list_widget)

            btn_box = QtWidgets.QHBoxLayout()
            ok_btn = QtWidgets.QPushButton("OK", dialog)
            cancel_btn = QtWidgets.QPushButton("Cancel", dialog)
            btn_box.addWidget(ok_btn)
            btn_box.addWidget(cancel_btn)
            layout.addLayout(btn_box)

            def on_ok():
                selected_items = list_widget.selectedItems()
                if selected_items:
                    preset_name = selected_items[0].text()
                    set_knobs_func(presets_dict[preset_name])
                    setattr(self, current_preset_attr, preset_name)
                    screen_label.setText(preset_name)
                    dialog.accept()
                else:
                    dlg = CustomMessageDialog("Select a preset", "Please select a preset.", parent=dialog)
                    dlg.exec_()

            ok_btn.clicked.connect(on_ok)
            cancel_btn.clicked.connect(dialog.reject)

            dialog.exec_()

        # === SAVE PRESET PROMPT ===
        def save_preset(presets_dict, get_knobs_func, current_preset_attr, screen_label):
            dialog = SavePresetDialog(getattr(self, current_preset_attr) or "", parent=self.mod_win)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                name = dialog.get_values()
                if not name:
                    return
                if name in presets_dict:
                    overwrite_dialog = QtWidgets.QMessageBox(self.mod_win)
                    overwrite_dialog.setWindowTitle("Overwrite?")
                    overwrite_dialog.setText(f"Preset '{name}' exists. Overwrite?")
                    overwrite_dialog.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                    overwrite_dialog.setStyleSheet("""QMessageBox { background:#121212; color:white; }""")
                    if overwrite_dialog.exec_() == QtWidgets.QMessageBox.No:
                        return
                presets_dict[name] = get_knobs_func()
                setattr(self, current_preset_attr, name)
                screen_label.setText(name)

                success = SuccessMessageDialog(f"Preset '{name}' saved.", parent=self.mod_win)
                success.setStyleSheet("background: transparent; padding: 4px 8px;")  # black bg with some padding
                success.exec_()
                self.save_mod_presets()  # persist changes


        # === UPDATE PRESET ===
        def update_preset(presets_dict, get_knobs_func, current_preset_attr, screen_label):
            name = getattr(self, current_preset_attr)
            if not name:
                QtWidgets.QMessageBox.warning(self.mod_win, "No preset selected", "Please select a preset first.")
                return
            presets_dict[name] = get_knobs_func()
            screen_label.setText(name)
            self.save_mod_presets()  # persist changes

        # === KNOBS DICTIONARIES TO LINK LABELS TO KNOBS ===
        bic_knobs = {
            "Rate": custom_knob("assets/knob_black.png", +90, label="Rate", x=539, y=50),
            "Depth": custom_knob("assets/knob_black.png", +90, label="Depth", x=410, y=50),
            "Tone": custom_knob("assets/knob_black.png", +90, label="Tone", x=279, y=50),
            "Mix": custom_knob("assets/knob_black.png", +90, label="Mix", x=152, y=50),
        }

        for name, knob in bic_knobs.items():
            knob.setValue(int(bic_value_map.get(name, 0)))
            knob.valueChanged.connect(lambda val, n=name: bic_value_map.update({n: val}))
            
        mod_knobs = {
            "Speed": custom_knob("assets/knob_gunmetal.png", +240, label="Speed", x=814, y=247),
            "Shape": custom_knob("assets/knob_gunmetal.png", +240, label="Shape", x=685, y=247),
            "Phase": custom_knob("assets/knob_gunmetal.png", +240, label="Phase", x=267, y=247),
            "Spread": custom_knob("assets/knob_gunmetal.png", +240, label="Spread", x=138, y=247),
        }

        for name, knob in mod_knobs.items():
            knob.setValue(int(mod_value_map.get(name, 0)))
            knob.valueChanged.connect(lambda val, n=name: mod_value_map.update({n: val}))
            
        ech_knobs = {
            "Time": custom_knob("assets/knob_gold.png", +145, label="Time", x=83, y=430),
            "FB": custom_knob("assets/knob_gold.png", +145, label="FB", x=181, y=430),
            "Tone": custom_knob("assets/knob_gold.png", +145, label="Tone", x=279, y=430),
            "Mod": custom_knob("assets/knob_gold.png", +145, label="Mod", x=377, y=430),
            "Mix": custom_knob("assets/knob_gold.png", +145, label="Mix", x=475, y=430),
            "Level": custom_knob("assets/knob_gold.png", +145, label="Level", x=573, y=430),
        }

        for name, knob in ech_knobs.items():
            knob.setValue(int(ech_value_map.get(name, 0)))
            knob.valueChanged.connect(lambda val, n=name: ech_value_map.update({n: val}))
            
        self.bic_knobs = bic_knobs
        self.mod_knobs = mod_knobs
        self.ech_knobs = ech_knobs    
            

        # -------- ABSOLUTE‑POSITION BLUE BUTTONS ------------------------
        # BiCorus buttons
       # bic_save    = _flat_btn("SAVE")      ; bic_save.move(697, 104)
       # bic_presets = _flat_btn("PRESETS")  ; bic_presets.move(794, 104)
        bic_bypass  = _toggle_btn("ACTIVE") ; bic_bypass.move(697, 113)  # under SAVE
       # bic_update  = _flat_btn("UPDATE")    ; bic_update.move(794, 134)  # right of bypass

        # ModuLator buttons
       # mod_save    = _flat_btn("SAVE")      ; mod_save.move(417, 296)
       # mod_presets = _flat_btn("PRESETS")  ; mod_presets.move(514, 296)
        mod_bypass  = _toggle_btn("ACTIVE") ; mod_bypass.move(417, 305)  # under SAVE
       # mod_update  = _flat_btn("UPDATE")    ; mod_update.move(514, 324)  # right of bypass

        # EchoSphere buttons
       # ech_save    = _flat_btn("SAVE")      ; ech_save.move(744, 474)
       # ech_presets = _flat_btn("PRESETS")  ; ech_presets.move(842, 474)
        ech_bypass  = _toggle_btn("ACTIVE") ; ech_bypass.move(744, 489)  # under SAVE
       # ech_update  = _flat_btn("UPDATE")    ; ech_update.move(842, 502)  # right of bypass

        # -------- ABSOLUTE‑POSITION SCREENS -----------------------------
        bic_screen = _screen() ; bic_screen.move(692,  51)
        mod_screen = _screen() ; mod_screen.move(413, 241)
        ech_screen = _screen() ; ech_screen.move(739, 424)

        # Set initial screen text to empty (no preset selected)
        bic_screen.setText("T r i C h o r u s")
        mod_screen.setText("S p a c e   I m a g e r")
        ech_screen.setText("8 0 s   T a p e   D e l a y")

        # Connect buttons to their functions:
       # bic_save.clicked.connect(lambda: save_preset(self.bic_presets, get_bic_knob_values, "bic_current_preset", bic_screen))
       # bic_presets.clicked.connect(lambda: show_preset_selector(self.bic_presets, set_bic_knob_values, "bic_current_preset", bic_screen))
       # bic_update.clicked.connect(lambda: update_preset(self.bic_presets, get_bic_knob_values, "bic_current_preset", bic_screen))

       # mod_save.clicked.connect(lambda: save_preset(self.mod_presets, get_mod_knob_values, "mod_current_preset", mod_screen))
       # mod_presets.clicked.connect(lambda: show_preset_selector(self.mod_presets, set_mod_knob_values, "mod_current_preset", mod_screen))
       # mod_update.clicked.connect(lambda: update_preset(self.mod_presets, get_mod_knob_values, "mod_current_preset", mod_screen))

       # ech_save.clicked.connect(lambda: save_preset(self.ech_presets, get_ech_knob_values, "ech_current_preset", ech_screen))
       # ech_presets.clicked.connect(lambda: show_preset_selector(self.ech_presets, set_ech_knob_values, "ech_current_preset", ech_screen))
       # ech_update.clicked.connect(lambda: update_preset(self.ech_presets, get_ech_knob_values, "ech_current_preset", ech_screen))

        # bring overlays to front
        for w in (
       #     bic_save, bic_presets, bic_bypass, bic_update,
       #     mod_save, mod_presets, mod_bypass, mod_update,
       #     ech_save, ech_presets, ech_bypass, ech_update,
            bic_screen, mod_screen, ech_screen
        ):
            w.raise_()

        close_btn = QtWidgets.QPushButton("CLOSE", self.mod_win)
        close_btn.setFixedSize(140, 35)
        close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #101010;
                color: #8fc2ff;
                border: .5px solid #2D58B5;
                border-radius: 1px;
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 3px;
            }
            QPushButton:hover {
                background: #3f7cff;
                color: #fff;
            }
            QPushButton:pressed {
                background: #1a1c20;
                color: #aaccff;
            }
        """)
        # Position at bottom center:
        close_btn.move(self.mod_win.width() // 2 - close_btn.width() // 2, self.mod_win.height() - 52)
        def on_close():
            if self.bic_current_preset:
                self.bic_presets[self.bic_current_preset] = get_bic_knob_values()
                self.save_bic_presets()
            if self.mod_current_preset:
                self.mod_presets[self.mod_current_preset] = get_mod_knob_values()
                self.save_mod_presets()
            if self.ech_current_preset:
                self.ech_presets[self.ech_current_preset] = get_ech_knob_values()
                self.save_ech_presets()
            self.overlay.close()

        close_btn.clicked.connect(on_close)
        self.mod_win.show()


        
    # ------------------------------------------------------------------
    # full‑screen Mode (1024×600) with dim overlay
    # ------------------------------------------------------------------          

    def _show_mode_page(self):
        # ---- dark overlay background ----
        self.overlay = QtWidgets.QWidget(self)
        self.overlay.setGeometry(self.rect())
        self.overlay.setStyleSheet("background: rgba(0, 0, 0, 220);")
        self.overlay.show()
        self.overlay.raise_()

        # ---- full screen widget with background image ----
        self.mode_win = QtWidgets.QWidget(self.overlay)
        self.mode_win.setFixedSize(1024, 600)
        self.mode_win.setStyleSheet("""
            QWidget {
                background-image: url("assets/mode_bg.png");
                background-repeat: no-repeat;
                background-position: center;
                background-size: cover;
            }
        """)
        self.mode_win.move(0, 0)
        self.mode_win.destroyed.connect(self.overlay.close)

        def create_click_box(x, y, w, h, callback):
            btn = QtWidgets.QPushButton(self.mode_win)
            btn.setGeometry(x, y, w, h)
            btn.setStyleSheet("background: rgba(0, 0, 0, 0); border: none;")
            btn.setCursor(QtCore.Qt.PointingHandCursor)

            def on_click():
                btn.setStyleSheet("background: rgba(100, 100, 100, 80); border: none;")
                QtCore.QTimer.singleShot(150, lambda: btn.setStyleSheet("background: rgba(0, 0, 0, 0); border: none;"))
                callback()

            btn.clicked.connect(on_click)
            return btn

        def open_presets():
            if hasattr(self, "overlay"):
                self.overlay.close()
        if hasattr(self, "sonisphere_win"):
            self.sonisphere_win.setParent(None)
            self.sonisphere_win.deleteLater()
            del self.sonisphere_win

        def open_sonisphere():
            self._show_sonisphere_page()

        def open_scenes():
            self._show_scenes_page()

        # Add the 3 transparent click boxes
        create_click_box(29, 38, 280, 523, open_presets)
        create_click_box(371, 38, 280, 523, open_sonisphere)
        create_click_box(710, 38, 280, 523, open_scenes)

        
        # ---- bottom row of buttons ----
        btn_mod = QtWidgets.QPushButton("MODULATION", self.mode_win)
        btn_dyn = QtWidgets.QPushButton("DYNAMICS", self.mode_win)
        btn_rout = QtWidgets.QPushButton("ROUTING/PANNING", self.mode_win)
        btn_sys = QtWidgets.QPushButton("SYSTEM SETTINGS", self.mode_win)

        for b in (btn_mod, btn_dyn, btn_rout, btn_sys):
            b.setFixedSize(200, 35)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: #101010;
                    color: #8fc2ff;
                    border: .5px solid #2D58B5;
                    border-radius: 1px;
                    font-size: 12px;
                    font-weight: 600;
                    letter-spacing: 3px;
                }
                QPushButton:hover {
                    background: #3f7cff;
                    color: #fff;
                }
                QPushButton:pressed {
                    background: #1a1c20;
                    color: #aaccff;
                }
            """)

        btn_mod.clicked.connect(self._show_modulation_page)
        btn_dyn.clicked.connect(self._show_dynamics_page)
        btn_rout.clicked.connect(self._show_routing_page)
        btn_sys.clicked.connect(self._show_system_menu)

        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.addStretch()
        bottom_row.addWidget(btn_mod)
        bottom_row.addWidget(btn_dyn)
        bottom_row.addWidget(btn_rout)
        bottom_row.addWidget(btn_sys)
        bottom_row.addStretch()
        bottom_row.setSpacing(18)
        bottom_row.setContentsMargins(10, 10, 10, 18)
        vbox = QtWidgets.QVBoxLayout(self.mode_win)
        vbox.addStretch()
        vbox.addLayout(bottom_row)


        self.mode_win.show()
        self.mode_win.raise_()


    def animate_open(self):
        effect = QGraphicsOpacityEffect()
        self.sonisphere_win.setGraphicsEffect(effect)
        self.sonisphere_win.raise_()         # Bring to front
        self.sonisphere_win.show()           # Make visible

        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(500)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.anim.start()


    def _show_sonisphere_page(self):
        # Reset the overlay if it's missing
        if not hasattr(self, 'overlay') or not self.overlay.isVisible():
            self.overlay = QtWidgets.QWidget(self)
            self.overlay.setGeometry(self.rect())
            self.overlay.setStyleSheet("background:rgba(0,0,0,200);")
            self.overlay.show()
            self.overlay.raise_()

        # Fully destroy any previous Sonisphere instance
        if hasattr(self, 'sonisphere_win'):
            self.sonisphere_win.setParent(None)
            self.sonisphere_win.deleteLater()
            del self.sonisphere_win

        if hasattr(self, 'mode_win') and self.mode_win.isVisible():
            self.mode_win.hide()


        # ---- full screen widget ----
        self.sonisphere_win = QtWidgets.QWidget(self.overlay)
        self.sonisphere_win.setFixedSize(1024, 600)
        self.sonisphere_win.setStyleSheet("background-color: black;")
        self.sonisphere_win.move(0, 0)
        self.sonisphere_win.destroyed.connect(self.overlay.close)

        # Create SoniSphere inside sonisphere_win
        self.xy_pad = SoniSphere(
            self.sonisphere_win,
            open_presets_callback=self._show_presets,
            go_home_callback=self._show_mode_page
        )
        self.xy_pad.move(0, 0)
        self.xy_pad.show()

        
        # ---- bottom row of buttons ----
        btn_mod = QtWidgets.QPushButton("MODULATION", self.mode_win)
        btn_dyn = QtWidgets.QPushButton("DYNAMICS", self.mode_win)
        btn_rout = QtWidgets.QPushButton("ROUTING/PANNING", self.mode_win)
        btn_sys = QtWidgets.QPushButton("SYSTEM SETTINGS", self.mode_win)

        for b in (btn_mod, btn_dyn, btn_rout, btn_sys):
            b.setFixedSize(200, 35)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            b.setStyleSheet("""
                QPushButton {
                    background: #101010;
                    color: #8fc2ff;
                    border: .5px solid #2D58B5;
                    border-radius: 1px;
                    font-size: 12px;
                    font-weight: 600;
                    letter-spacing: 3px;
                }
                QPushButton:hover {
                    background: #3f7cff;
                    color: #fff;
                }
                QPushButton:pressed {
                    background: #1a1c20;
                    color: #aaccff;
                }
            """)

        btn_mod.clicked.connect(self._show_modulation_page)
        btn_dyn.clicked.connect(self._show_dynamics_page)
        btn_rout.clicked.connect(self._show_routing_page)
        btn_sys.clicked.connect(self._show_system_menu)

        bottom_row = QtWidgets.QHBoxLayout()
        bottom_row.addStretch()
        bottom_row.addWidget(btn_mod)
        bottom_row.addWidget(btn_dyn)
        bottom_row.addWidget(btn_rout)
        bottom_row.addWidget(btn_sys)
        bottom_row.addStretch()
        bottom_row.setSpacing(18)
        bottom_row.setContentsMargins(10, 10, 10, 18)
        vbox = QtWidgets.QVBoxLayout(self.mode_win)
        vbox.addStretch()
        vbox.addLayout(bottom_row)


        self.animate_open()
        self.sonisphere_win.raise_()
        
    # ------------------------------------------------------------------
    # full‑screen sonisphere (1024×600) with dim overlay
    # ------------------------------------------------------------------           


# ──────────────────────────────────────────────
# CUSTOM WIDGET: SoniSphere
# ──────────────────────────────────────────────
class SoniSphere(QtWidgets.QWidget):
    def __init__(self, parent=None, bg_path="assets/xy_pad.gif", open_presets_callback=None, go_home_callback=None):
        super().__init__(parent)
        self.dragging = False
        self.secondary_dragging = False
        self.setFixedSize(1024, 600)
        self.setMouseTracking(True)
        center_x = self.width() / 2
        center_y = self.height() / 2
        self.cursor_pos = QtCore.QPointF(center_x - 20, center_y)
        self.secondary_pos = QtCore.QPointF(center_x + 20, center_y)
        self.overlay_pixmap = QtGui.QPixmap("assets/xy_overlay.png")
        self.cursor_img = QtGui.QPixmap("assets/main_cursor.png")
        self.secondary_img = QtGui.QPixmap("assets/secondary_cursor.png")
        self.cursor_img = self.cursor_img.scaled(42, 42, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.secondary_img = self.secondary_img.scaled(42, 42, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.cursor_bounds = QtCore.QRectF(285, 75, 450, 450)     # x, y, width, height
        self.secondary_bounds = QtCore.QRectF(285, 75, 450, 450)  # separate area

        self.open_presets_callback = open_presets_callback
        self.go_home_callback = go_home_callback

        # Background image or animation
        self.bg_is_gif = bg_path.lower().endswith(".gif")
        if self.bg_is_gif:
            self.movie = QtGui.QMovie(bg_path)
            self.movie.setScaledSize(QtCore.QSize(1100, 800))
            self.movie.frameChanged.connect(self.update)
            self.movie.start()
        else:
            self.bg_pixmap = QtGui.QPixmap(bg_path)

        # Store preset names per corner
        self.presets = {
            'top_left': "Preset 1",
            'top_right': "Preset 1",
            'bottom_left': "Preset 1",
            'bottom_right': "Preset 1"
        }

        # Create buttons and preset display labels per corner
        self._create_corner_ui()
        
                # ---- reset button in bottom-right corner ----
        reset_btn = QtWidgets.QPushButton("CENTER", self)
        reset_btn.setFixedSize(100, 32)
        reset_btn.move(self.width() - reset_btn.width() - 20, self.height() - reset_btn.height() - 20)
        home_btn = QtWidgets.QPushButton("HOME", self)
        home_btn.setFixedSize(100, 32)
        home_btn.move(self.width() - 230, self.height() - 52)  # next to CENTER
        home_btn.setCursor(QtCore.Qt.PointingHandCursor)
        home_btn.setStyleSheet(reset_btn.styleSheet())  # use same style
        home_btn.clicked.connect(self.go_home_callback)
        reset_btn.setCursor(QtCore.Qt.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #101010;
                color: #8fc2ff;
                border: 1px solid #2D58B5;
                border-radius: 2px;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 2px;
            }
            QPushButton:hover {
                background-color: #3f7cff;
                color: white;
            }
            QPushButton:pressed {
                background-color: #1a1c20;
                color: #aaccff;
            }
        """)
        reset_btn.clicked.connect(self.reset_positions)
        
    def _handle_button_click(self, corner, preset_index):
        print(f"Clicked button {preset_index} in {corner}")
        new_preset = f"Preset {preset_index}"
        self.update_preset(corner, new_preset)

        if self.open_presets_callback:
            self.open_presets_callback()        

    def reset_positions(self):
        center_x = self.width() / 2
        center_y = self.height() / 2
        self.cursor_pos = QtCore.QPointF(center_x - 20, center_y)
        self.secondary_pos = QtCore.QPointF(center_x + 20, center_y)
        self.update()        

    def clamp_point_to_circle(self, point, center, radius):
        dx = point.x() - center.x()
        dy = point.y() - center.y()
        dist = (dx**2 + dy**2)**0.5
        if dist > radius:
            scale = radius / dist
            clamped_x = center.x() + dx * scale
            clamped_y = center.y() + dy * scale
            return QtCore.QPointF(clamped_x, clamped_y)
        else:
            return point

    def _create_corner_ui(self):
        btn_w, btn_h = 100, 35
        label_w, label_h = 250, 30

        # Define the text for each button per corner
        button_texts = {
            'top_left':    ["PRESETS", "EDIT", "LFO", "ACTIVE"],
            'top_right':   ["PRESETS", "EDIT", "LFO", "ACTIVE"],
            'bottom_left': ["PRESETS", "EDIT", "LFO", "ACTIVE"],
            'bottom_right':["PRESETS", "EDIT", "LFO", "ACTIVE"],
        }

        # Individual positions for each button (x, y)
        button_positions = {
            'top_left': [
                (10, 130),
                (125, 130),
                (10, 180),
                (125, 180)
            ],
            'top_right': [
                (self.width() - 225, 130),
                (self.width() - 110, 130),
                (self.width() - 225, 180),
                (self.width() - 110, 180)
            ],
            'bottom_left': [
                (10, self.height() - 212),
                (125, self.height() - 212),
                (10, self.height() - 162),
                (125, self.height() - 162)
            ],
            'bottom_right': [
                (self.width() - 225, self.height() - 212),
                (self.width() - 110, self.height() - 212),
                (self.width() - 225, self.height() - 162),
                (self.width() - 110, self.height() - 162)
            ]
        }

        label_positions = {
            'top_left': (10, 79),
            'top_right': (self.width() - 280, 79),
            'bottom_left': (10, self.height() - 262),
            'bottom_right': (self.width() - 280, self.height() - 262)
        }

        self.buttons = {}
        self.labels = {}

        for corner in button_positions:
            self.buttons[corner] = []
            for i, (x, y) in enumerate(button_positions[corner]):
                btn = QtWidgets.QPushButton(button_texts[corner][i], self)
                btn.setGeometry(x, y, btn_w, btn_h)
                btn.setCursor(QtCore.Qt.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #ffffff;
                        border: .5px solid #555;
                        border-radius: 1px;
                        font-size: 10px;
                    }
                    QPushButton:hover {
                        background-color: #3f3f3f;
                    }
                """)
                btn.clicked.connect(lambda _, c=corner, idx=i: self.open_presets_page(f"{c}_{idx+1}"))
                self.buttons[corner].append(btn)

            label_x, label_y = label_positions[corner]
            label = QtWidgets.QLabel(self.presets[corner], self)
            label.setGeometry(label_x, label_y, label_w, label_h)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setStyleSheet("""
                background-color: transparent;
                color: #8ff;
                border-radius: 1px;
                font-size: 12px;
                font-weight: 600;
                padding: 6px 10px;
            """)
            self.labels[corner] = label

    def open_presets_page(self, corner):
        print(f"Opening presets page for {corner} (Current: {self.presets[corner]})")
        if self.open_presets_callback:
            self.open_presets_callback()

        # For demo: cycle preset name
        current_num = int(self.presets[corner].split()[-1])
        new_num = current_num % 10 + 1
        new_preset = f"Preset {new_num}"
        self.update_preset(corner, new_preset)

    def update_preset(self, corner, new_preset_name):
        self.presets[corner] = new_preset_name
        self.labels[corner].setText(new_preset_name)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if self.bg_is_gif:
            frame = self.movie.currentPixmap()
            gif_size = self.movie.scaledSize()
            x = (self.width() - gif_size.width()) // 2
            y = (self.height() - gif_size.height()) // 2
            painter.drawPixmap(x, y, frame)
        else:
            painter.drawPixmap(self.rect(), self.bg_pixmap)

        # ✅ Draw the PNG overlay on top (centered or full screen)
        if not self.overlay_pixmap.isNull():
            painter.drawPixmap(self.rect(), self.overlay_pixmap)

        # Finger cursor
        cursor_w = self.cursor_img.width()
        cursor_h = self.cursor_img.height()
        painter.drawPixmap(
                int(self.cursor_pos.x() - cursor_w / 2),
                int(self.cursor_pos.y() - cursor_h / 2),
                self.cursor_img
        )

        # Draw secondary cursor PNG
        sec_w = self.secondary_img.width()
        sec_h = self.secondary_img.height()
        painter.drawPixmap(
                int(self.secondary_pos.x() - sec_w / 2),
                int(self.secondary_pos.y() - sec_h / 2),
                self.secondary_img
        )

     #  # Quadrant labels
     #  font = QtGui.QFont("Audiowide", 14)
     #  painter.setFont(font)
     #  painter.setPen(QtGui.QColor("white"))
     #  painter.drawText(10, 20, "Reverb 1")
     #  painter.drawText(self.width() - 100, 20, "Reverb 2")
     #  painter.drawText(10, self.height() - 10, "Reverb 3")
     #  painter.drawText(self.width() - 120, self.height() - 10, "Reverb 4")
        
      # painter.setPen(QtGui.QPen(QtGui.QColor("#5555ff"), 1, QtCore.Qt.DashLine)) # <----------
      # painter.drawRect(self.cursor_bounds)                                       #             |

      # painter.setPen(QtGui.QPen(QtGui.QColor("#ff5555"), 1, QtCore.Qt.DashLine)) # <---------- Boundary Box Limit Finders
      # painter.drawRect(self.secondary_bounds)

    def mouseMoveEvent(self, event):
        center = QtCore.QPointF(self.width() / 2, self.height() / 2)
        radius = 200  # Change this to whatever size you want the circular boundary to be

        if self.dragging:
            new_pos = event.pos()
            self.cursor_pos = self.clamp_point_to_circle(new_pos, center, radius)
            self.update()

        elif self.secondary_dragging:
            new_pos = event.pos()
            self.secondary_pos = self.clamp_point_to_circle(new_pos, center, radius)
            self.update()

    def mousePressEvent(self, event):
        if (self.cursor_pos - event.pos()).manhattanLength() < 15:
            self.dragging = True
        elif (self.secondary_pos - event.pos()).manhattanLength() < 15:
            self.secondary_dragging = True    

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.secondary_dragging = False

    def calculate_blend(self):
        x = self.cursor_pos.x() / self.width()
        y = self.cursor_pos.y() / self.height()

        top = 1.0 - y
        bottom = y
        left = 1.0 - x
        right = x

        blend = {
            'A': left * top,
            'B': right * top,
            'C': left * bottom,
            'D': right * bottom
        }

        total = sum(blend.values())
        for k in blend:
            blend[k] /= total if total != 0 else 1

        return blend


    
 
# Run it
# ---------------------------------------------------------------------------

# ──────────────────────────────────────────────
# APPLICATION ENTRY POINT
# ──────────────────────────────────────────────
def main():
    app = QtWidgets.QApplication(sys.argv)
    ui = SpringHallUI()
    ui._show_mode_page()
    ui.show()
    sys.exit(app.exec_())
 
 
if __name__ == "__main__":
    main()