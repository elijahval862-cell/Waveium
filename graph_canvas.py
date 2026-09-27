from PySide6.QtCore import Qt, QTimer, Signal, QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient, QPixmap
from PySide6.QtWidgets import QWidget
import math


class WaveiumGraphCanvas(QWidget):
    """
    Waveium central network topology canvas.

    Important:
    - All discovered graph nodes are always drawn.
    - "Hide Names" hides ONLY device/router information cards.
    - Router, device icons, links, signal zones and animation remain visible.
    """

    device_selected = Signal(object)

    def __init__(self, graph=None, parent=None):
        super().__init__(parent)

        self.graph = graph
        self.show_details = True
        self.hovered_node = None
        self.selected_node = None
        self.animation_offset = 0
        self.node_positions = {}
        self.edge_values = {}
        self.dragging_node = None
        self.manual_positions = {}
        self.card_rects = {}
        self.coverage_info = None
        self._bg_cache = None

        self.setMinimumSize(0, 0)
        self.setMouseTracking(True)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.animate)
        self.animation_timer.start(50)

        self.rebuild_positions()

    # ----------------------------------------------------------
    # GRAPH API
    # ----------------------------------------------------------

    def set_graph(self, graph):
        self.graph = graph
        self.selected_node = None
        self.hovered_node = None
        self.manual_positions = {}
        self.rebuild_positions()
        self.update()

    def set_coverage_info(self, info):
        self.coverage_info = info
        self.update()

    def set_edge_signal(self, source, target, rssi):
        self.edge_values[(source, target)] = rssi
        self.edge_values[(target, source)] = rssi
        self.update()

    def set_edge_range(self, source, target, distance):
        self.update()

    def toggle_details(self):
        """Hide/show ONLY topology labels/cards."""
        self.show_details = not self.show_details
        self.update()

    # ----------------------------------------------------------
    # HELPERS
    # ----------------------------------------------------------

    def animate(self):
        self.animation_offset = (self.animation_offset + 3) % 600
        self.update()

    def get_router(self):
        if self.graph is None:
            return None

        for node, data in self.graph.nodes(data=True):
            role = str(data.get("role", "")).lower()
            vertex_type = str(data.get("vertex_type", "")).lower()
            label = str(data.get("label", "")).lower()

            if role == "router" or vertex_type == "router":
                return node

            if "main router" in label or "gateway" in label:
                return node

        return None

    def get_local_device(self):
        if self.graph is None:
            return None

        for node, data in self.graph.nodes(data=True):
            label = str(data.get("label", "")).upper()
            if label in ("YOUR DEVICE", "THIS DEVICE", "LOCAL DEVICE"):
                return node

            if str(data.get("role", "")).lower() == "local_device":
                return node

        return None

    def _safe_nodes(self):
        if self.graph is None:
            return []
        return list(self.graph.nodes(data=True))

    # ----------------------------------------------------------
    # POSITIONS
    # ----------------------------------------------------------

    def rebuild_positions(self):
        """
        Dynamically positions the network topology in a true, balanced CIRCULAR layout.
        Router stays perfectly centered, signal zones use the full central space,
        and devices are distributed with generous breathing room.
        """
        nodes = self._safe_nodes()

        if not nodes:
            self.node_positions = {}
            return

        width = max(self.width(), 300)
        height = max(self.height(), 300)

        # Router is the absolute visual anchor, dead center in the canvas
        cx = width * 0.50
        cy = height * 0.50

        router = self.get_router()
        local = self.get_local_device()

        positions = {}

        if router is not None:
            positions[router] = QPointF(cx, cy)

        client_nodes = [
            node
            for node, _ in nodes
            if node != router
        ]

        # Prioritize local device to sit at the primary reference position (top at 12 o'clock)
        if local is not None and local in client_nodes:
            client_nodes.remove(local)
            client_nodes.insert(0, local)

        # Sort remaining nodes deterministically by IP or label so positions remain stable
        if len(client_nodes) > 1:
            rest = client_nodes[1:]
            rest.sort(key=lambda n: str(self.graph.nodes.get(n, {}).get("ip", n)))
            client_nodes = [client_nodes[0]] + rest

        count = len(client_nodes)

        # Maximum device radius so cards (height 52 + 14px gap) always keep at least 14px margin from edges
        card_extent = 32 + 14 + 52  # 98px
        margin = 14
        max_device_r = max((height / 2) - card_extent - margin, 120.0)

        # Signal zones enlarge to use almost the entire central panel
        max_r = min(width, height) * 0.46
        base_r = min(max_device_r, max_r * 0.70)

        if count > 0:
            step_deg = 360.0 / count
            # Start angle at top (-90 degrees), placing local device at 12 o'clock
            start_deg = -90.0

            for index, node in enumerate(client_nodes):
                data = self.graph.nodes.get(node, {})
                rssi = data.get("rssi")

                if rssi is not None:
                    try:
                        r_val = float(rssi)
                        r_norm = max(0.0, min(1.0, (-40.0 - r_val) / 45.0))
                        radial_factor = 0.88 + 0.16 * r_norm
                    except (TypeError, ValueError):
                        radial_factor = 0.95
                else:
                    radial_factor = 0.95

                # Stagger radii slightly when 6+ devices are present to maximize breathing room
                if count >= 6:
                    stagger = 0.05 if (index % 2 == 0) else -0.05
                    radial_factor = max(0.82, min(1.04, radial_factor + stagger))

                angle = math.radians(start_deg + index * step_deg)

                dev_r = min(max_device_r, base_r * radial_factor)

                # Pure circular geometry: uniform radial span
                x = cx + dev_r * math.cos(angle)
                y = cy + dev_r * math.sin(angle)

                # Clamp comfortably inside canvas to prevent any border clipping
                x = max(75, min(width - 75, x))
                y = max(60, min(height - 60, y))

                positions[node] = QPointF(x, y)

        # Preserve any manual drag adjustments relative to center and scale
        if hasattr(self, "manual_positions") and self.manual_positions:
            for n, offset in self.manual_positions.items():
                if n in positions and isinstance(offset, (tuple, list)) and len(offset) == 2:
                    nx, ny = offset
                    positions[n] = QPointF(
                        max(50, min(width - 50, cx + nx * max_r)),
                        max(50, min(height - 50, cy + ny * max_r))
                    )

        self.node_positions = positions

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg_cache = None
        self.rebuild_positions()

    # ----------------------------------------------------------
    # PAINT
    # ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        self.draw_background(painter)

        router = self.get_router()
        if router in self.node_positions:
            self.draw_signal_zones(
                painter,
                self.node_positions[router]
            )

        self.draw_edges(painter)
        self.draw_particles(painter)
        self.draw_nodes(painter)
        self.draw_hud_overlays(painter)

        painter.end()

    def draw_background(self, painter):
        w = max(self.width(), 100)
        h = max(self.height(), 100)

        # Fast cached background rendering: eliminates thousands of draw calls per frame
        if self._bg_cache is None or self._bg_cache.size() != self.size():
            self._bg_cache = QPixmap(w, h)
            cache_painter = QPainter(self._bg_cache)
            cache_painter.setRenderHint(QPainter.Antialiasing)

            # Center matches exact router center
            center = QPointF(w * 0.50, h * 0.50)

            # Subtle multi-stop lavender-pearl radial vignette
            gradient = QRadialGradient(center, max(w, h) * 0.75)
            gradient.setColorAt(0.00, QColor("#FAF8FE"))
            gradient.setColorAt(0.35, QColor("#F6F3FC"))
            gradient.setColorAt(0.72, QColor("#EFEBF7"))
            gradient.setColorAt(1.00, QColor("#E7E2F3"))
            cache_painter.fillRect(self.rect(), QBrush(gradient))

            # Technical Inset Viewport Frame (inset 8px)
            cache_painter.setPen(QPen(QColor(108, 93, 211, 45), 1))
            cache_painter.setBrush(Qt.NoBrush)
            cache_painter.drawRoundedRect(8, 8, w - 16, h - 16, 16, 16)

            # Fine Crosshair Axis Lines through router center with subtle dashes
            axis_pen = QPen(QColor(108, 93, 211, 26), 1, Qt.DashLine)
            axis_pen.setDashPattern([3, 9])
            cache_painter.setPen(axis_pen)
            cache_painter.drawLine(18, int(center.y()), w - 18, int(center.y()))
            cache_painter.drawLine(int(center.x()), 18, int(center.x()), h - 18)

            # Modern precision dot matrix
            cache_painter.setPen(Qt.NoPen)
            cache_painter.setBrush(QColor(108, 93, 211, 24))
            for x in range(20, w - 10, 30):
                for y in range(20, h - 10, 30):
                    cache_painter.drawEllipse(
                        QPointF(x, y),
                        1.2,
                        1.2
                    )

            # Elegant Corner Framing Brackets (14px technical L-shaped markers)
            bracket_pen = QPen(QColor(108, 93, 211, 60), 1.6)
            cache_painter.setPen(bracket_pen)
            # Top-Left
            cache_painter.drawLine(20, 20, 34, 20)
            cache_painter.drawLine(20, 20, 20, 34)
            # Top-Right
            cache_painter.drawLine(w - 20, 20, w - 34, 20)
            cache_painter.drawLine(w - 20, 20, w - 20, 34)
            # Bottom-Left
            cache_painter.drawLine(20, h - 20, 34, h - 20)
            cache_painter.drawLine(20, h - 20, 20, h - 34)
            # Bottom-Right
            cache_painter.drawLine(w - 20, h - 20, w - 34, h - 20)
            cache_painter.drawLine(w - 20, h - 20, w - 20, h - 34)

            cache_painter.end()

        painter.drawPixmap(0, 0, self._bg_cache)

    def draw_signal_zones(self, painter, center):
        """
        Draws dynamic, circular radar coverage zones estimating the router's
        Wi-Fi propagation reach. Features a distinct inner circle (Core Zone),
        progressive coverage tiers, and clear range markers.
        """
        w = max(self.width(), 300)
        h = max(self.height(), 300)
        max_r = min(w, h) * 0.485

        # Signal coverage zones: Outer Limit (~30m) -> Fair (~22m) -> Good (~15m) -> Strong (~8m) -> Core (< 3m)
        zones = [
            (1.00, "#F43F5E", 6, 60, "Limit ~30m"),   # Max Coverage Limit (~30m / 3000cm)
            (0.82, "#F59E0B", 10, 70, "Fair ~22m"),   # Fair / Boundary (~22m)
            (0.64, "#0EA5E9", 14, 80, "Good ~15m"),   # Good / Reliable (~15m)
            (0.44, "#10B981", 18, 92, "Strong ~8m"),  # Strong / High-Speed (~8m)
            (0.24, "#6366F1", 24, 115, "Core < 3m"),  # Inner Circle Core (< 3m / 300cm)
        ]

        # Draw from outermost to innermost so fills layer naturally
        for frac, hex_col, fill_alpha, stroke_alpha, label in zones:
            r = max_r * frac
            base = QColor(hex_col)

            # Crisp dashed zone boundary ring
            pen = QPen(
                QColor(base.red(), base.green(), base.blue(), stroke_alpha),
                1.4 if frac == 0.24 else 1.2,
                Qt.DashLine
            )
            pen.setDashPattern([3, 5] if frac == 0.24 else [4, 6])
            painter.setPen(pen)

            painter.setBrush(
                QColor(base.red(), base.green(), base.blue(), fill_alpha)
            )
            painter.drawEllipse(center, r, r)

        # ── DISTINCT INNER CIRCLE ACCENT ──
        # High-visibility radar inner circle bounding the router's core coverage
        inner_r = max_r * 0.24
        inner_pen = QPen(QColor(99, 102, 241, 140), 1.6, Qt.DashLine)
        inner_pen.setDashPattern([3, 4])
        painter.setPen(inner_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, inner_r, inner_r)

        # Inner orbit ring (passing through spoke junction region)
        orbit_r = max_r * 0.44
        orbit_pen = QPen(QColor(16, 185, 129, 85), 1.0, Qt.DotLine)
        painter.setPen(orbit_pen)
        painter.drawEllipse(center, orbit_r, orbit_r)

        # Subtle router core aura around router
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(99, 102, 241, 35))
        painter.drawEllipse(center, max_r * 0.12, max_r * 0.12)

        # Clean technical distance tags angled in open radial space (~ -36 degrees)
        angle_rad = math.radians(-36)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        for frac, hex_col, _, _, label in zones:
            r = max_r * frac
            tag_x = center.x() + r * cos_a + 4
            tag_y = center.y() + r * sin_a - 1
            if 25 < tag_x < self.width() - 80 and 25 < tag_y < self.height() - 25:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(255, 255, 255, 185))
                painter.drawRoundedRect(int(tag_x - 3), int(tag_y - 8), 58, 13, 3, 3)

                self.draw_text(
                    painter,
                    label,
                    tag_x,
                    tag_y,
                    55,
                    hex_col,
                    6.5,
                    True,
                    Qt.AlignLeft
                )

    def draw_hud_overlays(self, painter):
        """
        Draw clean, modern HUD pills for topology radar status, router coverage
        estimate, and coverage distance legend.
        """
        # 1. Top-Left: Clean Frosted Radar Pill
        chip_w = 195
        chip_h = 30
        chip_x = 22
        chip_y = 20

        # Ambient micro-shadow + clean white pill
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 20, 70, 10))
        painter.drawRoundedRect(chip_x, chip_y + 1, chip_w, chip_h, 15, 15)

        painter.setPen(QPen(QColor("#E6E2F6"), 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(chip_x, chip_y, chip_w, chip_h, 15, 15)

        # Pulsing green radar beacon
        pulse = 0.5 + 0.5 * math.sin(self.animation_offset * 0.08)
        radar_green = QColor("#00D2A0")
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 210, 160, int(40 + 50 * pulse)))
        painter.drawEllipse(QPointF(chip_x + 16, chip_y + 15), 6.5, 6.5)

        painter.setBrush(radar_green)
        painter.drawEllipse(QPointF(chip_x + 16, chip_y + 15), 3.5, 3.5)

        node_count = len(self.graph.nodes) if self.graph else 0
        radar_label = f"TOPOLOGY RADAR  •  {node_count} ACTIVE"
        self.draw_text(
            painter,
            radar_label,
            chip_x + 28,
            chip_y + 19,
            chip_w - 34,
            "#5B4DF0",
            7.5,
            True,
            Qt.AlignLeft
        )

        # 2. Top-Right: Estimated Router Signal Coverage Pill
        cov_chip_w = 285
        cov_chip_h = 30
        cov_chip_x = self.width() - cov_chip_w - 22
        cov_chip_y = 20

        max_d = 30.0
        band_str = "5 GHz"
        if self.coverage_info:
            max_d = self.coverage_info.get("max_distance", 30.0)
            band_str = self.coverage_info.get("band", "5 GHz")

        if cov_chip_x > chip_x + chip_w + 10:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(30, 20, 70, 10))
            painter.drawRoundedRect(cov_chip_x, cov_chip_y + 1, cov_chip_w, cov_chip_h, 15, 15)

            painter.setPen(QPen(QColor("#E6E2F6"), 1))
            painter.setBrush(QColor(255, 255, 255, 235))
            painter.drawRoundedRect(cov_chip_x, cov_chip_y, cov_chip_w, cov_chip_h, 15, 15)

            # Signal beacon dot
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#6366F1"))
            painter.drawEllipse(QPointF(cov_chip_x + 16, cov_chip_y + 15), 3.5, 3.5)

            self.draw_text(
                painter,
                f"EST. ROUTER COVERAGE: ~{int(round(max_d))}m ({int(round(max_d*100))}cm) • {band_str}",
                cov_chip_x + 28,
                cov_chip_y + 19,
                cov_chip_w - 34,
                "#323062",
                7.5,
                True,
                Qt.AlignLeft
            )

        # 3. Bottom-Left: Spacious Frosted Legend with Clear Zone Colors & Distances
        legend_w = 380
        legend_h = 28
        legend_x = 22
        legend_y = self.height() - legend_h - 18

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(30, 20, 70, 10))
        painter.drawRoundedRect(legend_x, legend_y + 1, legend_w, legend_h, 14, 14)

        painter.setPen(QPen(QColor("#E8E5F6"), 1))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawRoundedRect(legend_x, legend_y, legend_w, legend_h, 14, 14)

        legend_items = [
            ("#6366F1", "Core (< 3m)"),
            ("#10B981", "Strong (8m)"),
            ("#0EA5E9", "Good (15m)"),
            ("#F59E0B", "Fair (22m)"),
            ("#F43F5E", "Limit (~30m)"),
        ]
        cur_x = legend_x + 12
        for dot_col, text in legend_items:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(dot_col))
            painter.drawEllipse(QPointF(cur_x + 2, legend_y + 14), 3.5, 3.5)

            self.draw_text(
                painter,
                text,
                cur_x + 10,
                legend_y + 18,
                64,
                "#4B4E6D",
                7.2,
                True,
                Qt.AlignLeft
            )
            cur_x += 72

    def get_edge_rssi(self, source, target):
        value = self.edge_values.get((source, target))
        if value is None:
            value = self.edge_values.get((target, source))

        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        if self.graph is not None:
            try:
                value = self.graph[source][target].get("rssi")
                if value is not None:
                    return float(value)
            except Exception:
                pass

        return None

    def signal_color(self, rssi):
        if rssi is None:
            return QColor("#6366F1")
        if rssi >= -55:
            return QColor("#00C48C")  # Emerald Strong
        if rssi >= -68:
            return QColor("#5B4DF0")  # Indigo Good
        if rssi >= -78:
            return QColor("#F59E0B")  # Amber Fair
        return QColor("#EF4444")      # Coral Limit

    def draw_edges(self, painter):

        if self.graph is None:
            return

        router = self.get_router()
        local = self.get_local_device()

        # Identify active connection (selected client node or local device)
        active_target = None
        if self.selected_node is not None and self.selected_node != router:
            active_target = self.selected_node
        elif local is not None and local in self.graph.nodes:
            active_target = local

        # Smooth breathing sine pulse for the active connection animation
        t = self.animation_offset * 0.08
        pulse = 0.5 + 0.5 * math.sin(t)

        for source, target in self.graph.edges():

            p1 = self.node_positions.get(source)
            p2 = self.node_positions.get(target)

            if p1 is None or p2 is None:
                continue

            rssi = self.get_edge_rssi(source, target)

            is_active = (
                active_target is not None
                and (
                    (source == router and target == active_target)
                    or (target == router and source == active_target)
                )
            )

            is_dimmed = (
                self.selected_node is not None
                and self.selected_node != router
                and not is_active
            )

            is_local_link = (
                local is not None
                and (source == local or target == local)
            )

            # Signal strength visually obvious mapping:
            # - Local / Excellent (>= -60): Vibrant Emerald Green (#00C48C), 2.2px solid
            # - Good (-61 to -72): Vibrant Purple (#5B4DF0), 2.0px solid
            # - Fair (-73 to -80): Warm Amber (#F59E0B), 2.0px solid
            # - Weak (< -80): Coral Red (#EF4444), 1.8px DASHED
            if is_local_link:
                color = QColor("#00C48C")
                width = 2.4
                dash_style = Qt.SolidLine
            elif rssi is None:
                color = QColor("#5B4DF0")
                width = 2.0
                dash_style = Qt.SolidLine
            elif rssi >= -60:
                color = QColor("#00C48C")
                width = 2.2
                dash_style = Qt.SolidLine
            elif rssi >= -72:
                color = QColor("#5B4DF0")
                width = 2.0
                dash_style = Qt.SolidLine
            elif rssi >= -80:
                color = QColor("#F59E0B")
                width = 2.0
                dash_style = Qt.SolidLine
            else:
                color = QColor("#EF4444")
                width = 1.8
                dash_style = Qt.DashLine

            if is_dimmed:
                # Dim background edges when a specific node is active/selected
                dim_pen = QPen(QColor(180, 175, 220, 80), 1.5, Qt.SolidLine, Qt.RoundCap)
                painter.setPen(dim_pen)
                painter.drawLine(p1, p2)
                continue

            if is_active:
                # --- ACTIVE CONNECTION: Dynamic Electric Pulse Glow ---
                # 1. Pulsing breathing outer aura
                glow_width = 10.0 + 6.0 * pulse
                glow_alpha = int(30 + 35 * pulse)
                active_glow_pen = QPen(
                    QColor(color.red(), color.green(), color.blue(), glow_alpha),
                    glow_width,
                    Qt.SolidLine,
                    Qt.RoundCap
                )
                painter.setPen(active_glow_pen)
                painter.drawLine(p1, p2)

                # 2. Concentrated inner beam
                inner_glow_pen = QPen(
                    QColor(color.red(), color.green(), color.blue(), 75),
                    5.5,
                    Qt.SolidLine,
                    Qt.RoundCap
                )
                painter.setPen(inner_glow_pen)
                painter.drawLine(p1, p2)

                # 3. Bright high-energy core line
                core_pen = QPen(
                    color,
                    3.0,
                    Qt.SolidLine,
                    Qt.RoundCap
                )
                painter.setPen(core_pen)
                painter.drawLine(p1, p2)

            else:
                # Standard clean network graph line with subtle micro-glow
                glow_pen = QPen(
                    QColor(color.red(), color.green(), color.blue(), 25),
                    width + 3.5,
                    Qt.SolidLine,
                    Qt.RoundCap
                )
                painter.setPen(glow_pen)
                painter.drawLine(p1, p2)

                core_pen = QPen(color, width, dash_style, Qt.RoundCap)
                if dash_style == Qt.DashLine:
                    core_pen.setDashPattern([5, 4])
                painter.setPen(core_pen)
                painter.drawLine(p1, p2)

            # Clean Network Graph Junction Node at midpoint
            mid_x = (p1.x() + p2.x()) * 0.5
            mid_y = (p1.y() + p2.y()) * 0.5
            painter.setPen(QPen(QColor("#FFFFFF"), 1.2))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(mid_x, mid_y), 3.0, 3.0)

    def draw_particles(self, painter):

        if self.graph is None:
            return

        router = self.get_router()
        local = self.get_local_device()
        active_target = None
        if self.selected_node is not None and self.selected_node != router:
            active_target = self.selected_node
        elif local is not None and local in self.graph.nodes:
            active_target = local

        for index, (source, target) in enumerate(self.graph.edges()):

            p1 = self.node_positions.get(source)
            p2 = self.node_positions.get(target)

            if p1 is None or p2 is None:
                continue

            rssi = self.get_edge_rssi(source, target)
            color = self.signal_color(rssi)
            if local is not None and (source == local or target == local):
                color = QColor("#00C48C")

            is_active = (
                active_target is not None
                and (
                    (source == router and target == active_target)
                    or (target == router and source == active_target)
                )
            )

            # Orient particles to flow from router outwards to devices
            start_p = p1 if source == router else p2
            end_p = p2 if source == router else p1

            if is_active:
                # Active connection has rapid dual energetic data packets
                for p_offset in (0, 250):
                    phase = ((self.animation_offset * 1.6 + p_offset) % 500) / 500.0
                    x = start_p.x() + (end_p.x() - start_p.x()) * phase
                    y = start_p.y() + (end_p.y() - start_p.y()) * phase

                    # Luminous particle aura
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(color.red(), color.green(), color.blue(), 85))
                    painter.drawEllipse(QPointF(x, y), 6.0, 6.0)

                    # Bright white particle core
                    painter.setBrush(QColor("#FFFFFF"))
                    painter.drawEllipse(QPointF(x, y), 2.8, 2.8)
            else:
                # Standard link calm particle
                phase = ((self.animation_offset + index * 125) % 500) / 500.0
                x = start_p.x() + (end_p.x() - start_p.x()) * phase
                y = start_p.y() + (end_p.y() - start_p.y()) * phase

                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), 50))
                painter.drawEllipse(QPointF(x, y), 4.5, 4.5)

                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), 2.4, 2.4)

    def draw_nodes(self, painter):
        if self.graph is None:
            return

        router = self.get_router()
        local = self.get_local_device()

        for node, data in self.graph.nodes(data=True):
            pos = self.node_positions.get(node)
            if pos is None:
                continue

            if node == router:
                self.draw_router(painter, node, data, pos)
            else:
                self.draw_device(
                    painter,
                    node,
                    data,
                    pos,
                    node == local
                )

    def draw_router(self, painter, node, data, pos):

        selected = self.selected_node == node
        hovered = self.hovered_node == node

        # 1. Dynamic Animated Radar Beacon Pulse Wave radiating from router center
        pulse_phase = (self.animation_offset % 200) / 200.0
        wave_r = 46.0 + pulse_phase * 38.0
        wave_alpha = int(55 * (1.0 - pulse_phase))
        painter.setPen(QPen(QColor(91, 77, 240, wave_alpha), 1.6))
        painter.setBrush(QColor(108, 93, 211, int(wave_alpha * 0.35)))
        painter.drawEllipse(pos, wave_r, wave_r)

        # 2. Outermost soft ambient aura (radius 68)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(108, 93, 211, 24))
        painter.drawEllipse(pos, 68, 68)

        # 3. Middle luminous halo ring (radius 56)
        painter.setBrush(QColor(238, 234, 255, 175))
        painter.drawEllipse(pos, 56, 56)

        border = (
            QColor("#3827D9")
            if selected
            else QColor("#4F46E5")
        )

        # 4. Core router node (radius 46) with subtle radial gradient
        core_grad = QRadialGradient(pos, 46)
        core_grad.setColorAt(0.0, QColor("#FFFFFF"))
        core_grad.setColorAt(1.0, QColor("#F3EFFE"))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(
            QPen(
                border,
                3.6 if selected else 3.0
            )
        )
        painter.drawEllipse(pos, 46, 46)

        # Inner concentric accent ring
        painter.setPen(QPen(QColor("#DDD6FE"), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(pos, 40.0, 40.0)

        self.draw_router_icon(painter, pos)

        if hovered:
            painter.setPen(QPen(QColor("#5B4DF0"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(pos, 56, 56)

        if self.show_details:
            self.draw_router_card(painter, data, pos)

    def draw_router_icon(self, painter, pos):

        c = QColor("#5B4DF0")

        # 3 Angled Antennas with tip nodes (scaled for 46px router)
        painter.setPen(QPen(c, 2.5, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(
            int(pos.x() - 12),
            int(pos.y() - 8),
            int(pos.x() - 18),
            int(pos.y() - 21)
        )
        painter.drawLine(
            int(pos.x()),
            int(pos.y() - 8),
            int(pos.x()),
            int(pos.y() - 22)
        )
        painter.drawLine(
            int(pos.x() + 12),
            int(pos.y() - 8),
            int(pos.x() + 18),
            int(pos.y() - 21)
        )

        # Antenna tip nodes
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#4F46E5"))
        painter.drawEllipse(QPointF(pos.x() - 18, pos.y() - 21), 2.2, 2.2)
        painter.drawEllipse(QPointF(pos.x(), pos.y() - 22), 2.2, 2.2)
        painter.drawEllipse(QPointF(pos.x() + 18, pos.y() - 21), 2.2, 2.2)

        # Router chassis box (42 x 19, radius 5)
        painter.setPen(QPen(c, 2.2))
        painter.setBrush(QColor("#FAF9FE"))
        painter.drawRoundedRect(
            int(pos.x() - 21),
            int(pos.y() - 6),
            42,
            19,
            5,
            5
        )

        # Chassis inner bevel line
        painter.setPen(QPen(QColor("#E2DCFD"), 1.2))
        painter.drawLine(
            int(pos.x() - 18),
            int(pos.y() + 4),
            int(pos.x() + 18),
            int(pos.y() + 4)
        )

        # 4 Distinct Illuminating Status LEDs:
        # LED 1: Power (Vibrant Emerald Green with glow)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 210, 160, 90))
        painter.drawEllipse(QPointF(pos.x() - 12, pos.y() - 1), 3.2, 3.2)
        painter.setBrush(QColor("#00D2A0"))
        painter.drawEllipse(QPointF(pos.x() - 12, pos.y() - 1), 2.0, 2.0)

        # LED 2: WAN / Internet (Vibrant Cyan with glow)
        painter.setBrush(QColor(0, 184, 217, 90))
        painter.drawEllipse(QPointF(pos.x() - 4, pos.y() - 1), 3.2, 3.2)
        painter.setBrush(QColor("#00B8D9"))
        painter.drawEllipse(QPointF(pos.x() - 4, pos.y() - 1), 2.0, 2.0)

        # LEDs 3 & 4: 2.4G & 5G Wi-Fi (Vibrant Violet)
        painter.setBrush(c)
        painter.drawEllipse(QPointF(pos.x() + 4, pos.y() - 1), 2.0, 2.0)
        painter.drawEllipse(QPointF(pos.x() + 12, pos.y() - 1), 2.0, 2.0)

    def draw_device(self, painter, node, data, pos, is_local):

        selected = self.selected_node == node
        hovered = self.hovered_node == node

        rssi = data.get("rssi")

        router = self.get_router()
        local = self.get_local_device()
        active_target = self.selected_node if (self.selected_node is not None and self.selected_node != router) else local
        is_active = (node == active_target)

        # Visual hierarchy outlines & sizes:
        # - Active Device: Radius 34, breathing animated aura
        # - Other Devices: Radius 30, clean, uniform, consistent
        if is_local:
            outline = QColor("#00C48C")  # Signature Emerald Green
        elif selected:
            outline = QColor("#5B4DF0")
        elif is_active:
            outline = QColor("#5B4DF0")
        else:
            outline = QColor("#6C5DD3")

        node_r = 34 if is_active else 30

        if is_active:
            # Active device breathing aura ring
            pulse = 0.5 + 0.5 * math.sin(self.animation_offset * 0.08)
            pulse_r = node_r + 8.0 + 4.0 * pulse
            pulse_a = int(30 + 35 * pulse)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(outline.red(), outline.green(), outline.blue(), pulse_a))
            painter.drawEllipse(pos, pulse_r, pulse_r)

        # Soft outer halo
        halo_r = node_r + (10 if is_active else 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(
            QColor(
                outline.red(),
                outline.green(),
                outline.blue(),
                28 if is_active else 20
            )
        )
        painter.drawEllipse(pos, halo_r, halo_r)

        # Core node circle with white fill
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(
            QPen(
                outline,
                3.0 if is_active else 2.2
            )
        )
        painter.drawEllipse(pos, node_r, node_r)

        self.draw_device_icon(
            painter,
            pos,
            data,
            is_local
        )

        status = self.signal_color(rssi)
        if is_local:
            status = QColor("#00C48C")

        # Top-right status indicator dot
        dot_offset = 21 if is_active else 19
        dot_r = 4.2 if is_active else 3.8
        painter.setPen(
            QPen(
                QColor("#FFFFFF"),
                1.5
            )
        )
        painter.setBrush(status)
        painter.drawEllipse(
            QPointF(
                pos.x() + dot_offset,
                pos.y() - dot_offset
            ),
            dot_r,
            dot_r
        )

        if hovered:
            painter.setPen(QPen(QColor("#5B4DF0"), 1.8))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(pos, node_r + 6, node_r + 6)

        if self.show_details:
            self.draw_device_card(
                painter,
                node,
                data,
                pos,
                is_local,
                is_active
            )

    def draw_device_icon(self, painter, pos, data, is_local):
        """
        Draw a device-specific icon.

        Waveium's scanner may not always know the exact hardware type,
        so the icon is selected from every useful text field available.
        The local machine defaults to a laptop/PC icon.
        """
        text = " ".join(
            str(data.get(key, ""))
            for key in (
                "label",
                "hostname",
                "name",
                "device_type",
                "type",
                "vendor",
                "manufacturer",
                "description",
                "model",
            )
        ).lower()

        # --------------------------------------------------
        # 1. Use explicit device information when available.
        # --------------------------------------------------
        if any(word in text for word in (
            "phone", "mobile", "android", "iphone", "ipad",
            "tablet", "galaxy", "pixel", "oneplus", "redmi"
        )):
            self.draw_phone_icon(painter, pos)
            return

        if any(word in text for word in (
            "tv", "television", "smarttv", "chromecast",
            "roku", "firetv", "bravia"
        )):
            self.draw_tv_icon(painter, pos)
            return

        if any(word in text for word in (
            "printer", "print", "laserjet", "deskjet"
        )):
            self.draw_printer_icon(painter, pos)
            return

        if any(word in text for word in (
            "camera", "cam", "cctv", "hikvision", "reolink"
        )):
            self.draw_camera_icon(painter, pos)
            return

        if any(word in text for word in (
            "speaker", "audio", "alexa", "echo", "sonos"
        )):
            self.draw_speaker_icon(painter, pos)
            return

        if any(word in text for word in (
            "desktop", "pc", "computer", "workstation"
        )):
            self.draw_desktop_icon(painter, pos)
            return

        # --------------------------------------------------
        # 2. Do NOT perform reverse-DNS here.
        #
        # Painting runs on the Qt GUI thread. A hostname lookup
        # can wait on the network and make the whole application
        # appear frozen. Device identification therefore uses
        # only metadata already supplied by the scanner.
        # --------------------------------------------------

        # --------------------------------------------------
        # 3. MAC-vendor hints. These are intentionally limited:
        #    a vendor alone cannot prove the exact hardware type.
        #    They are used only when no better identification exists.
        # --------------------------------------------------
        mac = str(data.get("mac", "")).replace("-", ":").lower()
        prefix = ":".join(mac.split(":")[:3])

        phone_prefixes = {
            "ac:37:43", "3c:5a:b4", "a4:83:e7",
            "b4:f1:da", "f0:18:98", "d8:bb:2c",
            "10:2a:b3", "78:02:f8"
        }

        tv_prefixes = {
            "00:1c:62", "7c:01:91", "b8:27:eb"
        }

        if prefix in phone_prefixes:
            self.draw_phone_icon(painter, pos)
            return

        if prefix in tv_prefixes:
            self.draw_tv_icon(painter, pos)
            return

        # Safe fallback.
        self.draw_laptop_icon(painter, pos)

    def draw_printer_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.0))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 15), int(pos.y() - 3),
            30, 17, 3, 3
        )
        painter.drawRect(
            int(pos.x() - 11), int(pos.y() - 15),
            22, 12
        )
        painter.drawLine(
            int(pos.x() - 8), int(pos.y() + 14),
            int(pos.x() + 8), int(pos.y() + 14)
        )

    def draw_camera_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.0))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 17), int(pos.y() - 9),
            34, 20, 4, 4
        )
        painter.drawRect(
            int(pos.x() - 8), int(pos.y() - 14),
            11, 5
        )
        painter.drawEllipse(
            QPointF(pos.x(), pos.y() + 1), 6, 6
        )

    def draw_speaker_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.0))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 11), int(pos.y() - 17),
            22, 34, 5, 5
        )
        painter.drawEllipse(
            QPointF(pos.x(), pos.y() - 5), 5, 5
        )
        painter.drawEllipse(
            QPointF(pos.x(), pos.y() + 9), 3, 3
        )

    def draw_laptop_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.1))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 14),
            int(pos.y() - 12),
            28,
            20,
            2,
            2
        )

        painter.drawLine(
            int(pos.x() - 19),
            int(pos.y() + 12),
            int(pos.x() + 19),
            int(pos.y() + 12)
        )

        painter.drawLine(
            int(pos.x() - 9),
            int(pos.y() + 15),
            int(pos.x() + 9),
            int(pos.y() + 15)
        )

    def draw_phone_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.1))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 10),
            int(pos.y() - 17),
            20,
            34,
            4,
            4
        )

        painter.drawEllipse(
            QPointF(pos.x(), pos.y() + 12), 2, 2
        )

    def draw_tv_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.1))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 17),
            int(pos.y() - 11),
            34,
            23,
            3,
            3
        )

        painter.drawLine(
            int(pos.x()),
            int(pos.y() + 12),
            int(pos.x()),
            int(pos.y() + 17)
        )

        painter.drawLine(
            int(pos.x() - 8),
            int(pos.y() + 17),
            int(pos.x() + 8),
            int(pos.y() + 17)
        )

    def draw_desktop_icon(self, painter, pos):
        c = QColor("#5B4DF0")
        painter.setPen(QPen(c, 2.1))
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            int(pos.x() - 17),
            int(pos.y() - 13),
            34,
            24,
            3,
            3
        )

        painter.drawLine(
            int(pos.x()),
            int(pos.y() + 11),
            int(pos.x()),
            int(pos.y() + 17)
        )

        painter.drawLine(
            int(pos.x() - 9),
            int(pos.y() + 17),
            int(pos.x() + 9),
            int(pos.y() + 17)
        )

    # ----------------------------------------------------------
    # CARDS / NAMES
    # ----------------------------------------------------------

    def draw_router_card(self, painter, data, pos):

        width = 168
        height = 52

        x = int(pos.x() - width / 2)
        # Position card strictly below router circle (router radius 46, 12px clean gap)
        y = int(pos.y() + 58)

        x = max(8, min(x, self.width() - width - 8))
        y = max(8, min(y, self.height() - height - 8))

        router = self.get_router()
        self.card_rects[router] = QRectF(x, y, width, height)

        self.draw_card(
            painter,
            x,
            y,
            width,
            height,
            selected=(
                self.selected_node == router
            )
        )

        ip = data.get("ip", data.get("address", ""))

        self.draw_text(
            painter,
            "MAIN ROUTER",
            x + 6,
            y + 14,
            width - 12,
            "#1E1F38",
            8.5,
            True,
            Qt.AlignCenter
        )

        self.draw_text(
            painter,
            str(ip),
            x + 6,
            y + 28,
            width - 12,
            "#2D3154",
            9.0,
            True,
            Qt.AlignCenter
        )

        max_d = 30.0
        if self.coverage_info:
            max_d = self.coverage_info.get("max_distance", 30.0)

        self.draw_badge(
            painter,
            x + 8,
            y + 33,
            width - 16,
            f"GATEWAY  •  EST. COVERAGE ~{int(round(max_d))}m",
            bg_color=QColor("#F2EFFF"),
            border_color=QColor("#DDD6FE"),
            text_color="#5B4DF0"
        )

    def draw_device_card(self, painter, node, data, pos, is_local, is_active=False):

        width = 148
        height = 52

        cx = self.width() * 0.50
        cy = self.height() * 0.50

        # Position card strictly OUTSIDE the node circle with clean breathing gap (12px)
        node_r = 34 if is_active else 30
        gap = 12

        if pos.y() <= cy:
            # Upper half: place cleanly ABOVE the node circle
            y = int(pos.y() - node_r - gap - height)
            if y < 8:
                y = int(pos.y() + node_r + gap)
        else:
            # Lower half: place cleanly BELOW the node circle
            y = int(pos.y() + node_r + gap)
            if y + height > self.height() - 8:
                y = int(pos.y() - node_r - gap - height)

        x = int(pos.x() - width / 2)
        x = max(8, min(x, self.width() - width - 8))
        y = max(8, min(y, self.height() - height - 8))

        self.card_rects[node] = QRectF(x, y, width, height)

        # Consistent card border styling
        is_card_highlighted = (
            self.selected_node == node
            or (is_local and self.selected_node is None)
        )
        border_col = None
        if is_local:
            border_col = QColor("#00C48C") if is_card_highlighted else QColor("#B8F2D5")
        elif is_card_highlighted:
            border_col = QColor("#5B4DF0")

        self.draw_card(
            painter,
            x,
            y,
            width,
            height,
            selected=is_card_highlighted,
            border_color=border_col
        )

        label = (
            "THIS COMPUTER"
            if is_local
            else str(
                data.get(
                    "label",
                    "DEVICE"
                )
            ).upper()
        )

        ip = data.get(
            "ip",
            node
        )

        # Line 1: Clean, consistent device label
        self.draw_text(
            painter,
            label,
            x + 6,
            y + 13,
            width - 12,
            "#00A878" if is_local else "#1E1F38",
            8.5 if is_local else 8.0,
            True,
            Qt.AlignCenter
        )

        # Line 2: Crisp, high-contrast IP address
        self.draw_text(
            painter,
            str(ip),
            x + 6,
            y + 26,
            width - 12,
            "#64748B",
            8.5,
            True,
            Qt.AlignCenter
        )

        # Line 3: Compact signal pill with consistent styling
        rssi = data.get("rssi")
        distance = data.get("distance")

        if rssi is not None:
            try:
                rssi_num = float(rssi)
                signal_text = f"RSSI {rssi_num:.0f} dBm"

                if is_local or rssi_num >= -60:
                    bg_col = QColor("#E6F9F0")
                    bd_col = QColor("#B8F2D5")
                    tx_col = "#00A878"
                elif rssi_num >= -72:
                    bg_col = QColor("#F0EDFF")
                    bd_col = QColor("#DED8FD")
                    tx_col = "#5B4DF0"
                else:
                    bg_col = QColor("#FFF7ED")
                    bd_col = QColor("#FFEDD5")
                    tx_col = "#D97706"
            except (TypeError, ValueError):
                signal_text = "Signal measured"
                bg_col = QColor("#F0EDFF")
                bd_col = QColor("#DED8FD")
                tx_col = "#5B4DF0"

            if distance is not None:
                try:
                    d_val = float(distance)
                    if d_val <= 5.0:
                        signal_text += f"  •  {d_val * 100:.0f}cm"
                    else:
                        signal_text += f"  •  {d_val:.1f}m"
                except (TypeError, ValueError):
                    pass
        else:
            signal_text = "Signal unmeasured"
            bg_col = QColor("#F8FAFC")
            bd_col = QColor("#E2E8F0")
            tx_col = "#64748B"

        self.draw_badge(
            painter,
            x + 8,
            y + 32,
            width - 16,
            signal_text,
            bg_color=bg_col,
            border_color=bd_col,
            text_color=tx_col
        )

    def draw_card(self, painter, x, y, width, height, selected=False, border_color=None):

        # Multi-layer ambient drop shadow
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(22, 18, 55, 10))
        painter.drawRoundedRect(
            x + 1,
            y + 2,
            width,
            height,
            10,
            10
        )

        if border_color is not None:
            border = border_color
        elif selected:
            border = QColor("#5B4DF0")
        else:
            border = QColor("#EAE7F6")

        painter.setPen(
            QPen(
                border,
                1.8 if selected else 1.0
            )
        )
        painter.setBrush(QColor("#FFFFFF"))

        painter.drawRoundedRect(
            x,
            y,
            width,
            height,
            10,
            10
        )

    def draw_badge(
        self,
        painter,
        x,
        y,
        width,
        text,
        bg_color=None,
        border_color=None,
        text_color=None
    ):
        if bg_color is None:
            bg_color = QColor("#F0EDFF")
        if border_color is None:
            border_color = QColor("#DED8FD")
        if text_color is None:
            text_color = "#5B4DF0"

        painter.setPen(
            QPen(
                border_color,
                1.0
            )
        )
        painter.setBrush(bg_color)

        painter.drawRoundedRect(
            x,
            y,
            width,
            16,
            8,
            8
        )

        self.draw_text(
            painter,
            text,
            x + 2,
            y + 11,
            width - 4,
            text_color,
            7.0,
            True,
            Qt.AlignCenter
        )

    def draw_text(
        self,
        painter,
        text,
        x,
        baseline,
        width,
        color,
        size,
        bold=False,
        alignment=Qt.AlignLeft
    ):
        font = QFont("Segoe UI")
        font.setPointSizeF(size)
        font.setBold(bold)

        painter.setFont(font)
        painter.setPen(QColor(color))

        painter.drawText(
            int(x),
            int(baseline - size + 1),
            int(width),
            int(size + 5),
            alignment,
            str(text)
        )

    # ----------------------------------------------------------
    # MOUSE & DRAGGING
    # ----------------------------------------------------------

    def find_node_at(self, position):
        router = self.get_router()
        for node, node_position in self.node_positions.items():
            distance = math.hypot(
                position.x() - node_position.x(),
                position.y() - node_position.y()
            )

            hit_r = 50 if node == router else 36
            if distance <= hit_r:
                return node

        if hasattr(self, "card_rects") and self.show_details:
            for node, rect in self.card_rects.items():
                if rect.contains(position):
                    return node

        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        node = self.find_node_at(event.position())

        if node is not None:
            self.selected_node = node
            self.dragging_node = None
            self.device_selected.emit(node)
        else:
            self.selected_node = None
            self.dragging_node = None

        self.update()

    def mouseMoveEvent(self, event):
        # Nodes are stationary and locked in place (dragging disabled)
        node = self.find_node_at(event.position())

        if node != self.hovered_node:
            self.hovered_node = node
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging_node = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Double clicking resets any manual drags back to perfect balanced circle
        if hasattr(self, "manual_positions"):
            self.manual_positions.clear()
        self.rebuild_positions()
        self.update()
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        self.hovered_node = None
        self.dragging_node = None
        self.update()
        super().leaveEvent(event)
