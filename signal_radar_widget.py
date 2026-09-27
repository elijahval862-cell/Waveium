"""
Waveium Signal Advisor - Live Animated Coverage Radar & Distance Track Widget
Visualizes real-time Wi-Fi propagation, coverage boundaries, user device position,
and animated movement guidance vectors.
"""

import math
from PySide6.QtCore import Qt, QPointF, QRectF, QTimer
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QRadialGradient,
    QLinearGradient, QPainterPath
)
from PySide6.QtWidgets import QWidget


class SignalRadarTrackWidget(QWidget):
    """
    Animated radar and distance track widget for the Signal Advisor.
    Shows animated Wi-Fi radio waves, coverage threshold zones,
    current device position, and dynamic movement vectors.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(240)
        self.setMaximumHeight(270)

        self.rssi = -53
        self.signal_percent = 94
        self.distance_m = 3.03
        self.quality = "EXCELLENT"

        self.animation_offset = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(40)  # 25 FPS smooth animation

    def _tick(self):
        self.animation_offset = (self.animation_offset + 1) % 600
        self.update()

    def update_state(self, rssi, distance_m, signal_percent=None, quality=None):
        """Update live telemetry for the animated radar."""
        if rssi is not None:
            try:
                self.rssi = int(rssi)
            except (TypeError, ValueError):
                pass

        if distance_m is not None:
            try:
                self.distance_m = float(distance_m)
            except (TypeError, ValueError):
                pass

        if signal_percent is not None:
            try:
                self.signal_percent = int(signal_percent)
            except (TypeError, ValueError):
                pass

        if quality is not None:
            self.quality = str(quality).upper()

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w = self.width()
        h = self.height()

        # ── 1. MAIN CARD CONTAINER ──
        bg_rect = QRectF(0, 0, w, h)
        painter.setPen(QPen(QColor("#ECECF6"), 1.2))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRoundedRect(bg_rect.adjusted(1, 1, -1, -1), 18, 18)

        # ── 2. HEADER: TITLE & LIVE PULSE BADGE ──
        painter.setPen(QColor("#11142D"))
        title_font = QFont("Segoe UI", 11, QFont.Bold)
        painter.setFont(title_font)
        painter.drawText(22, 28, "LIVE COVERAGE SPECTRUM & DISTANCE TRACK")

        sub_font = QFont("Segoe UI", 9, QFont.Normal)
        painter.setFont(sub_font)
        painter.setPen(QColor("#808191"))
        painter.drawText(22, 45, "Real-time RF wave propagation, coverage boundary & movement vector")

        # Live Pulse Badge on top right
        pulse_alpha = int(170 + 75 * math.sin(self.animation_offset * 0.12))
        badge_w, badge_h = 135, 24
        badge_rect = QRectF(w - badge_w - 22, 16, badge_w, badge_h)
        painter.setPen(QPen(QColor(5, 166, 96, pulse_alpha), 1))
        painter.setBrush(QColor(230, 249, 240, 200))
        painter.drawRoundedRect(badge_rect, 12, 12)

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor("#05A660"))
        painter.drawText(badge_rect, Qt.AlignCenter, "●  RF RADAR ACTIVE")

        # ── 3. TRACK LAYOUT GEOMETRY ──
        router_x = 55
        track_y = 125
        track_start_x = 120
        track_end_x = w - 45
        track_w = max(100, track_end_x - track_start_x)

        # Maximum scale on track is 15.0 meters
        max_track_dist = 15.0

        def dist_to_x(d):
            clamped = max(0.0, min(max_track_dist, d))
            return track_start_x + (clamped / max_track_dist) * track_w

        # Threshold distances:
        # Core (Peak): 2.4m (240 cm)
        # Good Coverage Limit: 5.5m (550 cm)
        # Fair Limit: 10.0m
        # Weak / Drop-off: > 10.0m
        x_core = dist_to_x(2.4)
        x_good = dist_to_x(5.5)
        x_fair = dist_to_x(10.0)

        # ── 4. ANIMATED WI-FI RADIO WAVES (FROM ROUTER) ──
        router_center = QPointF(router_x, track_y)

        # Concentric animated wave arcs expanding towards the track
        for i in range(4):
            wave_phase = (self.animation_offset * 1.8 + i * 28) % 110
            r = 18 + wave_phase
            alpha = max(0, int(180 * (1.0 - wave_phase / 110.0)))
            wave_color = QColor(91, 77, 240, alpha)

            painter.setPen(QPen(wave_color, 1.8, Qt.SolidLine, Qt.RoundCap))
            painter.setBrush(Qt.NoBrush)

            # Arc facing right (from -65 deg to +65 deg)
            arc_rect = QRectF(router_center.x() - r, router_center.y() - r, 2 * r, 2 * r)
            painter.drawArc(arc_rect, -65 * 16, 130 * 16)

        # Draw Router Icon
        painter.setPen(QPen(QColor("#5B4DF0"), 2.2))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawEllipse(router_center, 22, 22)

        # Mini router glyph inside circle
        painter.setPen(QPen(QColor("#5B4DF0"), 1.8))
        rx, ry = router_center.x(), router_center.y()
        painter.drawRoundedRect(QRectF(rx - 10, ry - 3, 20, 10), 3, 3)
        painter.drawLine(QPointF(rx - 5, ry - 3), QPointF(rx - 7, ry - 9))
        painter.drawLine(QPointF(rx + 5, ry - 3), QPointF(rx + 7, ry - 9))

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor("#11142D"))
        painter.drawText(QRectF(router_x - 35, track_y + 26, 70, 20), Qt.AlignCenter, "ROUTER")
        painter.setFont(QFont("Segoe UI", 7, QFont.Normal))
        painter.setPen(QColor("#808191"))
        painter.drawText(QRectF(router_x - 35, track_y + 40, 70, 15), Qt.AlignCenter, "0 cm")

        # ── 5. MULTI-ZONE SPECTRUM TRACK BAR ──
        bar_h = 14
        bar_top = track_y - bar_h / 2

        # Draw track background shadow/groove
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#F0EDF9"))
        painter.drawRoundedRect(QRectF(track_start_x, bar_top, track_w, bar_h), 7, 7)

        # Zone 1: Core Zone (0 to 2.4m / 240cm) -> Emerald
        z1_w = max(0, x_core - track_start_x)
        grad1 = QLinearGradient(track_start_x, 0, x_core, 0)
        grad1.setColorAt(0.0, QColor("#05A660"))
        grad1.setColorAt(1.0, QColor("#00D2A0"))
        painter.setBrush(grad1)
        painter.drawRoundedRect(QRectF(track_start_x, bar_top, z1_w, bar_h), 7, 7)

        # Zone 2: Good Coverage Zone (2.4m to 5.5m / 550cm) -> Cyan/Blue
        z2_w = max(0, x_good - x_core)
        grad2 = QLinearGradient(x_core, 0, x_good, 0)
        grad2.setColorAt(0.0, QColor("#00D2A0"))
        grad2.setColorAt(1.0, QColor("#3B82F6"))
        painter.setBrush(grad2)
        painter.drawRect(QRectF(x_core, bar_top, z2_w, bar_h))

        # Zone 3: Fair Zone (5.5m to 10.0m) -> Amber
        z3_w = max(0, x_fair - x_good)
        grad3 = QLinearGradient(x_good, 0, x_fair, 0)
        grad3.setColorAt(0.0, QColor("#3B82F6"))
        grad3.setColorAt(0.5, QColor("#FFB547"))
        grad3.setColorAt(1.0, QColor("#FF8A34"))
        painter.setBrush(grad3)
        painter.drawRect(QRectF(x_good, bar_top, z3_w, bar_h))

        # Zone 4: Weak Zone (10.0m to 15.0m) -> Rose / Red
        z4_w = max(0, track_end_x - x_fair)
        grad4 = QLinearGradient(x_fair, 0, track_end_x, 0)
        grad4.setColorAt(0.0, QColor("#FF8A34"))
        grad4.setColorAt(1.0, QColor("#FF5A79"))
        painter.setBrush(grad4)
        painter.drawRoundedRect(QRectF(x_fair, bar_top, z4_w, bar_h), 7, 7)

        # Re-clip boundary ends cleanly
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(track_start_x, bar_top, track_w, bar_h), 7, 7)

        # ── 6. THRESHOLD MARKERS & LABELS (CM & M) ──
        thresholds = [
            (track_start_x, "0 cm", "Router"),
            (x_core, "240 cm", "Core Limit"),
            (x_good, "550 cm (5.5 m)", "★ Good Coverage Limit"),
            (x_fair, "10.0 m", "Fair Limit"),
            (track_end_x, "15.0 m", "Drop-off"),
        ]

        for x_pos, dist_lbl, name_lbl in thresholds:
            # Tick mark
            painter.setPen(QPen(QColor("#808191"), 1.2))
            painter.drawLine(QPointF(x_pos, bar_top + bar_h), QPointF(x_pos, bar_top + bar_h + 6))

            # Labels below
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            painter.setPen(QColor("#11142D"))
            painter.drawText(QRectF(x_pos - 45, bar_top + bar_h + 8, 90, 14), Qt.AlignCenter, dist_lbl)

            painter.setFont(QFont("Segoe UI", 6, QFont.Normal))
            painter.setPen(QColor("#808191"))
            painter.drawText(QRectF(x_pos - 45, bar_top + bar_h + 20, 90, 13), Qt.AlignCenter, name_lbl)

        # ── 7. GOOD COVERAGE BOUNDARY GUIDE LINE ──
        # Prominent vertical dashed line marking 5.5 m (550 cm)
        painter.setPen(QPen(QColor("#3B82F6"), 1.8, Qt.DashLine))
        painter.drawLine(QPointF(x_good, 60), QPointF(x_good, track_y + 35))

        # Boundary Badge at top
        bdg_w, bdg_h = 150, 18
        bdg_rect = QRectF(x_good - bdg_w / 2, 56, bdg_w, bdg_h)
        painter.setPen(QPen(QColor("#3B82F6"), 1))
        painter.setBrush(QColor("#EBF2FE"))
        painter.drawRoundedRect(bdg_rect, 6, 6)
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.setPen(QColor("#2563EB"))
        painter.drawText(bdg_rect, Qt.AlignCenter, "GOOD COVERAGE: ≤ 550 cm")

        # ── 8. DEVICE POSITION PIN & LIVE MOVING VECTOR ──
        cur_dist = max(0.1, float(self.distance_m))
        cur_x = dist_to_x(cur_dist)

        # Color based on signal
        if self.rssi >= -50:
            dev_color = QColor("#05A660")
            status_text = "EXCELLENT"
        elif self.rssi >= -60:
            dev_color = QColor("#3B82F6")
            status_text = "GOOD"
        elif self.rssi >= -70:
            dev_color = QColor("#FFB547")
            status_text = "FAIR"
        else:
            dev_color = QColor("#FF5A79")
            status_text = "WEAK"

        # Animated pulse ring around device pin
        dev_pulse_r = 14 + 6 * math.sin(self.animation_offset * 0.15)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(dev_color.red(), dev_color.green(), dev_color.blue(), 55))
        painter.drawEllipse(QPointF(cur_x, track_y), dev_pulse_r, dev_pulse_r)

        # Device Pin Circle
        painter.setPen(QPen(QColor("#FFFFFF"), 2.5))
        painter.setBrush(dev_color)
        painter.drawEllipse(QPointF(cur_x, track_y), 9, 9)

        # Device Callout Tooltip Bubble (Above Track)
        # Format distance in cm if <= 5.0m
        if cur_dist <= 5.0:
            cm_val = int(round(cur_dist * 100))
            dist_str = f"{cm_val} cm"
        else:
            dist_str = f"{cur_dist:.2f} m"

        bubble_text = f"YOU ARE HERE: {dist_str}  •  {self.rssi} dBm"
        bubble_w = 210
        bubble_h = 24
        bubble_x = max(10, min(w - bubble_w - 10, cur_x - bubble_w / 2))
        bubble_y = track_y - 48

        bubble_rect = QRectF(bubble_x, bubble_y, bubble_w, bubble_h)
        painter.setPen(QPen(dev_color, 1.2))
        painter.setBrush(QColor("#11142D"))
        painter.drawRoundedRect(bubble_rect, 7, 7)

        # Pointer arrow down
        pointer = QPainterPath()
        pointer.moveTo(cur_x, track_y - 12)
        pointer.lineTo(cur_x - 5, bubble_y + bubble_h)
        pointer.lineTo(cur_x + 5, bubble_y + bubble_h)
        pointer.closeSubpath()
        painter.setBrush(QColor("#11142D"))
        painter.drawPath(pointer)

        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(bubble_rect, Qt.AlignCenter, bubble_text)

        # ── 9. DYNAMIC MOVEMENT GUIDANCE VECTOR (ARROW) ──
        # If user is within Good Coverage (<= 5.5m):
        # Show safe buffer arrow forward towards 5.5m limit
        # If user is outside Good Coverage (> 5.5m):
        # Show animated warning arrow pointing BACK towards 5.5m limit!
        arrow_y = track_y + 48

        if cur_dist <= 5.5:
            # Inside Good Coverage -> Display safe forward buffer
            buffer_dist = 5.5 - cur_dist
            if buffer_dist <= 5.0:
                buf_str = f"{int(round(buffer_dist * 100))} cm"
            else:
                buf_str = f"{buffer_dist:.2f} m"

            vec_start_x = cur_x
            vec_end_x = x_good

            # Draw arrow line if there is visible space
            if vec_end_x - vec_start_x > 18:
                anim_arrow_offset = (self.animation_offset * 1.5) % 16
                painter.setPen(QPen(QColor("#05A660"), 2.2, Qt.DashLine))
                painter.drawLine(QPointF(vec_start_x + 10, arrow_y), QPointF(vec_end_x - 6, arrow_y))

                # Arrowhead pointing right towards boundary
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#05A660"))
                ah = QPainterPath()
                ah.moveTo(vec_end_x, arrow_y)
                ah.lineTo(vec_end_x - 8, arrow_y - 4)
                ah.lineTo(vec_end_x - 8, arrow_y + 4)
                ah.closeSubpath()
                painter.drawPath(ah)

            # Advice text
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor("#05A660"))
            advice_str = f"✔ Safe Range Buffer: You can move up to {buf_str} farther and retain Good coverage"
            painter.drawText(QRectF(track_start_x, arrow_y + 8, track_w, 20), Qt.AlignLeft, advice_str)

        else:
            # Outside Good Coverage -> Advice to move closer
            needed_dist = cur_dist - 5.5
            if needed_dist <= 5.0:
                needed_str = f"{int(round(needed_dist * 100))} cm"
            else:
                needed_str = f"{needed_dist:.2f} m"

            vec_start_x = cur_x
            vec_end_x = x_good

            # Pulsing arrow pointing LEFT towards 5.5m limit
            pulse_warn = int(180 + 75 * math.sin(self.animation_offset * 0.2))
            warn_color = QColor(255, 90, 121, pulse_warn)

            painter.setPen(QPen(warn_color, 2.5, Qt.SolidLine))
            painter.drawLine(QPointF(vec_start_x - 8, arrow_y), QPointF(vec_end_x + 6, arrow_y))

            # Arrowhead pointing LEFT
            ah = QPainterPath()
            ah.moveTo(vec_end_x, arrow_y)
            ah.lineTo(vec_end_x + 8, arrow_y - 4)
            ah.lineTo(vec_end_x + 8, arrow_y + 4)
            ah.closeSubpath()
            painter.setBrush(warn_color)
            painter.drawPath(ah)

            # Warning advice text
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.setPen(QColor("#FF5A79"))
            advice_str = f"⚠️ Weak Coverage Warning: Move approximately {needed_str} closer to router to restore Good connection"
            painter.drawText(QRectF(track_start_x, arrow_y + 8, track_w, 20), Qt.AlignLeft, advice_str)

        painter.end()
