"""
Waveium Analytics - Custom Interactive Network Health & Signal Distribution Widget
Renders visual signal distribution bars, frequency spectrum, and health gauges.
"""

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QPainterPath
)
from PySide6.QtWidgets import QWidget


class NetworkAnalyticsChartWidget(QWidget):
    """
    Renders visual network analytics:
    1. Signal Quality Distribution Chart (binned device counts)
    2. Network Health Gauge & Radio Spectrum Quality
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setMaximumHeight(280)

        # Default sample/initial data
        self.distribution = {
            "Excellent": 3,
            "Good": 2,
            "Fair": 1,
            "Weak": 0
        }
        self.health_score = 96
        self.latency_ms = 4
        self.link_efficiency = 98

    def update_data(self, distribution=None, health_score=None, latency_ms=None, link_efficiency=None):
        if distribution is not None:
            self.distribution = distribution
        if health_score is not None:
            self.health_score = health_score
        if latency_ms is not None:
            self.latency_ms = latency_ms
        if link_efficiency is not None:
            self.link_efficiency = link_efficiency
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()

        # Background card
        painter.setPen(QPen(QColor("#ECECF6"), 1.2))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 18, 18)

        # ── LEFT PANEL: SIGNAL DISTRIBUTION BARS (60% width) ──
        left_w = int(w * 0.60)
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.setPen(QColor("#11142D"))
        painter.drawText(22, 28, "SIGNAL QUALITY DISTRIBUTION")

        painter.setFont(QFont("Segoe UI", 9, QFont.Normal))
        painter.setPen(QColor("#808191"))
        painter.drawText(22, 45, "Distribution of all connected nodes across RF signal tiers")

        bars = [
            ("Excellent", self.distribution.get("Excellent", 0), "#05A660", "#00D2A0", "≥ -50 dBm"),
            ("Good", self.distribution.get("Good", 0), "#3B82F6", "#60A5FA", "-51 to -60 dBm"),
            ("Fair", self.distribution.get("Fair", 0), "#FFB547", "#FBBF24", "-61 to -70 dBm"),
            ("Weak", self.distribution.get("Weak", 0), "#FF5A79", "#F87171", "< -70 dBm"),
        ]

        total_nodes = max(1, sum(b[1] for b in bars))
        max_count = max(1, max(b[1] for b in bars))

        start_y = 65
        row_h = 40
        label_w = 75
        max_bar_w = left_w - label_w - 110

        for i, (tier_name, count, c_start, c_end, tier_range) in enumerate(bars):
            y = start_y + i * row_h

            # Label
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QColor("#11142D"))
            painter.drawText(QRectF(22, y + 2, label_w, 18), Qt.AlignLeft | Qt.AlignVCenter, tier_name)

            # Sub-range label
            painter.setFont(QFont("Segoe UI", 7, QFont.Normal))
            painter.setPen(QColor("#808191"))
            painter.drawText(QRectF(22, y + 19, label_w, 14), Qt.AlignLeft | Qt.AlignVCenter, tier_range)

            # Bar
            bar_x = 22 + label_w + 12
            bar_y = y + 8
            calc_w = int((count / max(1, max_count)) * max_bar_w) if count > 0 else 8
            calc_w = max(10, min(max_bar_w, calc_w))

            # Bar track
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#F5F4FA"))
            painter.drawRoundedRect(QRectF(bar_x, bar_y, max_bar_w, 14), 7, 7)

            if count > 0:
                grad = QLinearGradient(bar_x, 0, bar_x + calc_w, 0)
                grad.setColorAt(0.0, QColor(c_start))
                grad.setColorAt(1.0, QColor(c_end))
                painter.setBrush(grad)
                painter.drawRoundedRect(QRectF(bar_x, bar_y, calc_w, 14), 7, 7)

            # Count pill on the right
            pct = int(round((count / total_nodes) * 100))
            count_text = f"{count} dev ({pct}%)"
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor(c_start) if count > 0 else QColor("#A0AEC0"))
            painter.drawText(QRectF(bar_x + max_bar_w + 10, y + 6, 80, 18), Qt.AlignLeft | Qt.AlignVCenter, count_text)

        # ── DIVIDER LINE ──
        painter.setPen(QPen(QColor("#ECECF6"), 1))
        painter.drawLine(QPointF(left_w, 20), QPointF(left_w, h - 20))

        # ── RIGHT PANEL: HEALTH SCORE & SPECTRUM QUALITY ──
        right_start_x = left_w + 24
        right_w = w - right_start_x - 22

        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.setPen(QColor("#11142D"))
        painter.drawText(right_start_x, 28, "NETWORK HEALTH INDEX")

        painter.setFont(QFont("Segoe UI", 9, QFont.Normal))
        painter.setPen(QColor("#808191"))
        painter.drawText(right_start_x, 45, "Composite score of RF stability, latency & bandwidth")

        # Circular Gauge Center
        gauge_cx = right_start_x + 60
        gauge_cy = 135
        gauge_r = 46

        # Gauge Track (Gray arc)
        painter.setPen(QPen(QColor("#F0EDF9"), 8, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(QRectF(gauge_cx - gauge_r, gauge_cy - gauge_r, 2 * gauge_r, 2 * gauge_r), -45 * 16, 270 * 16)

        # Gauge Active Arc (Green/Purple gradient)
        active_span = int((self.health_score / 100.0) * 270)
        painter.setPen(QPen(QColor("#05A660"), 8, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(QRectF(gauge_cx - gauge_r, gauge_cy - gauge_r, 2 * gauge_r, 2 * gauge_r), -45 * 16, active_span * 16)

        # Center Score Text
        painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
        painter.setPen(QColor("#11142D"))
        painter.drawText(QRectF(gauge_cx - 40, gauge_cy - 16, 80, 24), Qt.AlignCenter, f"{self.health_score}")
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor("#05A660"))
        painter.drawText(QRectF(gauge_cx - 40, gauge_cy + 8, 80, 16), Qt.AlignCenter, "/ 100")

        # Metrics on the right of the gauge
        diag_x = gauge_cx + gauge_r + 25
        diag_w = max(100, right_start_x + right_w - diag_x)

        diag_items = [
            ("RF Stability", "Optimal (≥ 95%)", "#05A660"),
            ("Est. Latency", f"~{self.latency_ms} ms (Ultra-low)", "#3B82F6"),
            ("Link Efficiency", f"{self.link_efficiency}% (PHY Cap)", "#5B4DF0"),
            ("Interference Risk", "Minimal (Isolated)", "#05A660"),
        ]

        dy_start = 75
        for idx, (lbl, val, col) in enumerate(diag_items):
            cur_y = dy_start + idx * 36
            painter.setFont(QFont("Segoe UI", 8, QFont.Normal))
            painter.setPen(QColor("#808191"))
            painter.drawText(QRectF(diag_x, cur_y, diag_w, 14), Qt.AlignLeft, lbl)

            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QColor(col))
            painter.drawText(QRectF(diag_x, cur_y + 14, diag_w, 16), Qt.AlignLeft, val)

        painter.end()
