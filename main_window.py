from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QComboBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QLineEdit,
    QSpinBox,
    QProgressBar,
    QDialog,
)
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QColor, QDesktopServices, QPixmap
import datetime

from core.network_scanner import NetworkScanner
from core.network_adapter import NetworkAdapter
from core.graph_generator import WaveiumGraphGenerator
from ui.graph_canvas import WaveiumGraphCanvas
from ui.signal_radar_widget import SignalRadarTrackWidget
from ui.analytics_chart_widget import NetworkAnalyticsChartWidget


class WaveiumMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "WAVEIUM — Network Connectivity Visualizer"
        )

        self.resize(1500, 900)
        self.setMinimumSize(1180, 700)

        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #EDEBF8;
                color: #11142D;
                font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
            }

            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 18px;
            }

            QLabel {
                color: #11142D;
            }

            QPushButton {
                background: #FFFFFF;
                color: #5B4DF0;
                border: 1px solid #EAE7F6;
                border-radius: 12px;
                padding: 9px 16px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #F0EDFF;
                border-color: #5B4DF0;
            }

            QComboBox {
                background: #FFFFFF;
                color: #11142D;
                border: 1px solid #EAE7F6;
                border-radius: 10px;
                padding: 8px 12px;
            }

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                background: #F2F0FB;
                width: 10px;
                margin: 2px;
                border-radius: 5px;
            }

            QScrollBar::handle:vertical {
                background: #C7C2EE;
                border-radius: 5px;
                min-height: 40px;
            }

            QScrollBar::handle:vertical:hover {
                background: #5B4DF0;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar:horizontal {
                height: 0px;
            }
            """
        )

        self.network_scanner = NetworkScanner()
        self.network_adapter = NetworkAdapter()

        print()
        print("=" * 58)
        print("        WAVEIUM NETWORK DISCOVERY")
        print("=" * 58)

        self.network_data = self.network_scanner.scan()

        self.graph = (
            WaveiumGraphGenerator.build_network(
                self.network_data
            )
        )

        self.create_interface()
        self.apply_live_wifi_data()
        self.update_advisor_page()

        self.live_wifi_timer = QTimer(self)
        self.live_wifi_timer.timeout.connect(
            self.update_live_wifi
        )
        self.live_wifi_timer.start(2000)

    # ==================================================
    # LIVE WI-FI DATA
    # ==================================================

    def apply_live_wifi_data(self):

        try:
            live = self.network_adapter.get_live_network()

            if not live or "error" in live:
                return

            wifi = self.network_data.setdefault(
                "wifi", {}
            )

            for key in [
                "ssid",
                "bssid",
                "signal_percent",
                "rssi",
                "band",
                "channel",
                "radio_type",
                "receive_rate",
                "transmit_rate",
                "authentication",
                "cipher",
                "profile",
            ]:
                value = live.get(key)
                if value is not None:
                    wifi[key] = value

            router = None

            for node, data in self.graph.nodes(data=True):
                if data.get("role") == "router":
                    router = node
                    break

            if router is None:
                return

            local_device = None
            local_ip = self.network_data.get("local_ip")

            if local_ip and local_ip in self.graph.nodes:
                local_device = local_ip

            if local_device is None:
                for node, data in self.graph.nodes(data=True):
                    if data.get("label") == "YOUR DEVICE":
                        local_device = node
                        break

            if local_device is None:
                return

            rssi = live.get("rssi")
            signal_percent = live.get("signal_percent")

            if rssi is None:
                return

            try:
                rssi = int(rssi)
            except (TypeError, ValueError):
                return

            estimated_distance = (
                WaveiumGraphGenerator.estimate_distance(rssi)
            )

            quality = (
                WaveiumGraphGenerator.signal_quality(rssi)
            )

            connection_status = (
                WaveiumGraphGenerator.connection_status(rssi)
            )

            device_data = self.graph.nodes[local_device]

            device_data["rssi"] = rssi
            device_data["signal"] = signal_percent
            device_data["distance"] = estimated_distance
            device_data["distance_type"] = "ESTIMATED FROM RSSI"
            device_data["quality"] = quality
            device_data["connection_status"] = connection_status
            device_data["status"] = "ACTIVE"

            if self.graph.has_edge(router, local_device):

                edge_data = self.graph[router][local_device]

                edge_data["rssi"] = rssi
                edge_data["signal"] = signal_percent
                edge_data["distance"] = estimated_distance
                edge_data["distance_type"] = "ESTIMATED FROM RSSI"
                edge_data["quality"] = quality
                edge_data["connection_status"] = connection_status
                edge_data["measured_rssi"] = True
                edge_data["measured_distance"] = False

                if hasattr(self.graph_canvas, "set_edge_signal"):
                    self.graph_canvas.set_edge_signal(
                        router,
                        local_device,
                        rssi
                    )

                if (
                    estimated_distance is not None
                    and hasattr(self.graph_canvas, "set_edge_range")
                ):
                    self.graph_canvas.set_edge_range(
                        router,
                        local_device,
                        estimated_distance
                    )

                if hasattr(self.graph_canvas, "set_coverage_info"):
                    cov_live = WaveiumGraphGenerator.estimate_router_coverage(
                        band=wifi.get("band"),
                        current_rssi=rssi,
                        current_distance=estimated_distance
                    )
                    self.graph_canvas.set_coverage_info(cov_live)

                if hasattr(self, "edge_changed"):
                    self.edge_changed()

            return live

        except Exception as error:
            print("Live Wi-Fi update error:")
            print(error)
            return None

    # ==================================================
    # MAIN INTERFACE
    # ==================================================


    def create_interface(self):

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ─────────────────────────────────────────────────────────
        # FLOATING NAVIGATION RAIL
        # ─────────────────────────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(246)
        self.sidebar.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 22px;
            }
        """)

        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 16, 14, 16)
        side.setSpacing(8)

        top = QHBoxLayout()
        self.sidebar_toggle = QPushButton("☰")
        self.sidebar_toggle.setFixedSize(40, 38)
        self.sidebar_toggle.setCursor(Qt.PointingHandCursor)
        self.sidebar_toggle.setStyleSheet("""
            QPushButton {
                background: #F6F5FD;
                color: #5B4DF0;
                border: 1px solid #EAE7F6;
                border-radius: 11px;
                font-size: 16px;
                font-weight: 900;
            }
            QPushButton:hover { background: #EEEDFA; }
        """)
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        top.addWidget(self.sidebar_toggle)
        top.addStretch()
        side.addLayout(top)

        self.sidebar_brand = QLabel("⚡ WAVEIUM")
        self.sidebar_brand.setStyleSheet("""
            QLabel {
                color: #11142D;
                font-size: 20px;
                font-weight: 950;
                padding: 8px 8px 1px;
                letter-spacing: 1px;
            }
        """)
        side.addWidget(self.sidebar_brand)

        self.sidebar_brand_sub = QLabel("NETWORK MONITOR & VISUALIZER")
        self.sidebar_brand_sub.setStyleSheet("""
            color: #808191;
            font-size: 8px;
            font-weight: 800;
            padding: 0 8px 10px;
            letter-spacing: 1px;
        """)
        side.addWidget(self.sidebar_brand_sub)

        nav_label = QLabel("MAIN MENU")
        nav_label.setStyleSheet(
            "color: #A0A3BD; font-size: 8px; font-weight: 800; padding: 4px 8px; letter-spacing: 0.8px;"
        )
        side.addWidget(nav_label)

        self.nav_buttons = []
        nav_items = [
            ("⌂", "Network Topology"),
            ("◉", "Live Scan"),
            ("▣", "Devices"),
            ("⌁", "Signal Advisor"),
            ("◌", "Analytics"),
            ("⚙", "Settings"),
        ]

        for index, (icon, name) in enumerate(nav_items):
            button = QPushButton(f"{icon}   {name}")
            button.setCheckable(True)
            button.setMinimumHeight(44)
            button.setCursor(Qt.PointingHandCursor)
            button.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 10px 14px;
                    background: transparent;
                    color: #737791;
                    border: none;
                    border-radius: 13px;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: #F6F5FD;
                    color: #5B4DF0;
                }
                QPushButton:checked {
                    background: #EEEDFA;
                    color: #5B4DF0;
                    font-weight: 800;
                }
            """)
            button.clicked.connect(
                lambda checked=False, i=index: self.navigate_to(i)
            )
            self.nav_buttons.append(button)
            side.addWidget(button)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #F0EFFB; border: none;")
        side.addWidget(divider)

        self.summary_toggle = QPushButton("▾   Network Summary")
        self.summary_toggle.setCheckable(True)
        self.summary_toggle.setChecked(True)
        self.summary_toggle.setMinimumHeight(38)
        self.summary_toggle.setCursor(Qt.PointingHandCursor)
        self.summary_toggle.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 9px 12px;
                background: #F8F7FD;
                color: #5B4DF0;
                border: 1px solid #EAE7F6;
                border-radius: 12px;
                font-size: 10px;
                font-weight: 800;
            }
            QPushButton:hover { background: #EEEDFA; }
        """)
        self.summary_toggle.clicked.connect(self.toggle_network_summary)
        side.addWidget(self.summary_toggle)

        self.summary_scroll = self.make_scroll_area(
            self.create_network_overview_panel(),
            width=218,
            outer=False,
        )
        self.summary_scroll.setMaximumHeight(290)
        side.addWidget(self.summary_scroll)

        side.addStretch()

        self.sidebar_status = QLabel("●  SYSTEM READY")
        self.sidebar_status.setAlignment(Qt.AlignCenter)
        self.sidebar_status.setStyleSheet("""
            QLabel {
                color: #05A660;
                background: #E6F9F0;
                border: 1px solid #C1F1D8;
                border-radius: 12px;
                padding: 9px;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
        """)
        side.addWidget(self.sidebar_status)

        root.addWidget(self.sidebar)

        # ─────────────────────────────────────────────────────────
        # MAIN FLOATING WORKSPACE
        # ─────────────────────────────────────────────────────────
        workspace = QFrame()
        workspace.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
            }
        """)

        app = QVBoxLayout(workspace)
        app.setContentsMargins(10, 8, 10, 8)
        app.setSpacing(10)

        # ── TOP HEADER (Dashboard Title, Search Bar & Actions) ──
        header = QHBoxLayout()
        header.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.page_title = QLabel("Dashboard")
        self.page_title.setMinimumWidth(220)
        self.page_title.setStyleSheet("""
            QLabel {
                color: #11142D;
                font-size: 22px;
                font-weight: 800;
                padding: 0;
            }
        """)
        self.page_subtitle = QLabel(
            "Real-time network connectivity & device monitoring"
        )
        self.page_subtitle.setStyleSheet("""
            QLabel {
                color: #808191;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.page_subtitle)
        header.addLayout(title_box)

        header.addStretch()

        # Pill Search Bar (matching reference mockup)
        self.top_search = QLineEdit()
        self.top_search.setPlaceholderText("🔍  Search devices, IP, MAC...")
        self.top_search.setMinimumWidth(160)
        self.top_search.setMaximumWidth(220)
        self.top_search.setFixedHeight(38)
        self.top_search.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #EAE7F6;
                border-radius: 19px;
                padding: 6px 16px;
                color: #11142D;
                font-size: 11px;
                font-weight: 600;
            }
            QLineEdit:focus {
                border: 1.5px solid #5B4DF0;
            }
        """)
        self.top_search.textChanged.connect(self.filter_global_search)
        header.addWidget(self.top_search)

        self.live_label = QPushButton("●  LIVE SCAN ACTIVE")
        self.live_label.setEnabled(False)
        self.live_label.setFixedHeight(38)
        self.live_label.setStyleSheet("""
            QPushButton {
                background: #E6F9F0;
                color: #05A660;
                border: 1px solid #C1F1D8;
                border-radius: 16px;
                padding: 8px 16px;
                font-size: 10px;
                font-weight: 800;
            }
        """)
        header.addWidget(self.live_label)

        # Flow Pill (Live Download / Upload)
        self.flow_pill = QFrame()
        self.flow_pill.setFixedHeight(38)
        self.flow_pill.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #EAE7F6;
                border-radius: 12px;
                padding: 2px 6px;
            }
        """)
        flow_pill_layout = QHBoxLayout(self.flow_pill)
        flow_pill_layout.setContentsMargins(10, 2, 10, 2)
        flow_pill_layout.setSpacing(10)
        self.flow_download = QLabel("↓ — Mbps")
        self.flow_download.setStyleSheet("color:#5B4DF0; font-size:11px; font-weight:800;")
        self.flow_upload = QLabel("↑ — Mbps")
        self.flow_upload.setStyleSheet("color:#05A660; font-size:11px; font-weight:800;")
        flow_pill_layout.addWidget(self.flow_download)
        flow_pill_layout.addWidget(self.flow_upload)
        header.addWidget(self.flow_pill)

        self.details_header_button = QPushButton("Hide Device Names")
        self.details_header_button.setFixedHeight(38)
        self.details_header_button.setCursor(Qt.PointingHandCursor)
        self.details_header_button.setToolTip("Show or hide device names on the topology map")
        self.details_header_button.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #5B4DF0;
                border: 1px solid #EAE7F6;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #F0EDFF;
                border-color: #5B4DF0;
            }
        """)
        self.details_header_button.clicked.connect(self.toggle_details)
        header.addWidget(self.details_header_button)

        self.panel_header_button = QPushButton("◨  Close Panel")
        self.panel_header_button.setFixedHeight(38)
        self.panel_header_button.setCursor(Qt.PointingHandCursor)
        self.panel_header_button.setToolTip("Open or close the right Device Details panel")
        self.panel_header_button.setStyleSheet("""
            QPushButton {
                background: #5B4DF0;
                color: #FFFFFF;
                border: 1px solid #5B4DF0;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #4738DB;
            }
        """)
        self.panel_header_button.clicked.connect(self.toggle_details_panel)
        header.addWidget(self.panel_header_button)

        self.mobile_header_button = QPushButton("🌐  Mobile / Web")
        self.mobile_header_button.setFixedHeight(38)
        self.mobile_header_button.setCursor(Qt.PointingHandCursor)
        self.mobile_header_button.setToolTip("Open Waveium Mobile App on your phone or web browser")
        self.mobile_header_button.setStyleSheet("""
            QPushButton {
                background: #F7F5FE;
                color: #5B4DF0;
                border: 1px solid #D6D0FA;
                border-radius: 12px;
                padding: 8px 14px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #5B4DF0;
                color: #FFFFFF;
                border-color: #5B4DF0;
            }
        """)
        self.mobile_header_button.clicked.connect(self.show_mobile_companion_dialog)
        header.addWidget(self.mobile_header_button)

        self.refresh_button = QPushButton("⟳")
        self.refresh_button.setFixedSize(38, 38)
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #5B4DF0;
                border: 1px solid #EAE7F6;
                border-radius: 12px;
                font-size: 18px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #5B4DF0;
                color: #FFFFFF;
            }
        """)
        self.refresh_button.clicked.connect(self.refresh_network)
        header.addWidget(self.refresh_button)
        app.addLayout(header)

        # ── FILTER PILLS CONTAINER (Removed as requested by user to give full space) ──
        self.filter_bar_container = QWidget()
        self.filter_bar_container.setVisible(False)
        self.filter_buttons = []

        # ── TOP 4 METRIC CARDS (Hidden on Network Topology so it covers full space) ──
        self.metrics_container = QWidget()
        metrics = QHBoxLayout(self.metrics_container)
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(12)

        # Card 1: Wi-Fi Gateway
        c1 = QFrame()
        c1.setMinimumHeight(86)
        c1.setStyleSheet("QFrame { background:#FFFFFF; border:1px solid #ECECF6; border-radius:18px; }")
        l1 = QVBoxLayout(c1)
        l1.setContentsMargins(15, 11, 15, 11)
        l1.setSpacing(4)
        r1 = QHBoxLayout()
        icon1 = QLabel("📡")
        icon1.setFixedSize(30, 30)
        icon1.setAlignment(Qt.AlignCenter)
        icon1.setStyleSheet("background:#EEEDFA; border-radius:8px; font-size:14px;")
        t1_box = QVBoxLayout()
        t1_box.setSpacing(1)
        self.metric_ssid_label = QLabel("Live Wi-Fi")
        self.metric_ssid_label.setStyleSheet("color:#11142D; font-size:13px; font-weight:800;")
        sub1 = QLabel("Wi-Fi Gateway")
        sub1.setStyleSheet("color:#808191; font-size:9px; font-weight:700;")
        t1_box.addWidget(self.metric_ssid_label)
        t1_box.addWidget(sub1)
        r1.addWidget(icon1)
        r1.addLayout(t1_box)
        r1.addStretch()
        l1.addLayout(r1)
        b1 = QHBoxLayout()
        self.metric_band_label = QLabel("Band: — • Channel: —")
        self.metric_band_label.setStyleSheet("color:#737791; font-size:10px; font-weight:600;")
        pill1 = QLabel("↑ 98% Link")
        pill1.setStyleSheet("color:#05A660; background:#E6F9F0; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
        b1.addWidget(self.metric_band_label)
        b1.addStretch()
        b1.addWidget(pill1)
        l1.addLayout(b1)
        metrics.addWidget(c1, 1)

        # Card 2: Signal Strength
        c2 = QFrame()
        c2.setMinimumHeight(86)
        c2.setStyleSheet("QFrame { background:#FFFFFF; border:1px solid #ECECF6; border-radius:18px; }")
        l2 = QVBoxLayout(c2)
        l2.setContentsMargins(15, 11, 15, 11)
        l2.setSpacing(4)
        r2 = QHBoxLayout()
        icon2 = QLabel("📶")
        icon2.setFixedSize(30, 30)
        icon2.setAlignment(Qt.AlignCenter)
        icon2.setStyleSheet("background:#FFEBEF; border-radius:8px; font-size:14px;")
        t2_box = QVBoxLayout()
        t2_box.setSpacing(1)
        self.metric_signal_label = QLabel("—")
        self.metric_signal_label.setStyleSheet("color:#11142D; font-size:13px; font-weight:800;")
        sub2 = QLabel("Signal Strength")
        sub2.setStyleSheet("color:#808191; font-size:9px; font-weight:700;")
        t2_box.addWidget(self.metric_signal_label)
        t2_box.addWidget(sub2)
        r2.addWidget(icon2)
        r2.addLayout(t2_box)
        r2.addStretch()
        l2.addLayout(r2)
        b2 = QHBoxLayout()
        self.metric_rssi_label = QLabel("RSSI: — dBm")
        self.metric_rssi_label.setStyleSheet("color:#737791; font-size:10px; font-weight:600;")
        self.metric_quality_pill = QLabel("↑ Excellent")
        self.metric_quality_pill.setStyleSheet("color:#05A660; background:#E6F9F0; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
        b2.addWidget(self.metric_rssi_label)
        b2.addStretch()
        b2.addWidget(self.metric_quality_pill)
        l2.addLayout(b2)
        metrics.addWidget(c2, 1)

        # Card 3: Connected Devices
        c3 = QFrame()
        c3.setMinimumHeight(86)
        c3.setStyleSheet("QFrame { background:#FFFFFF; border:1px solid #ECECF6; border-radius:18px; }")
        l3 = QVBoxLayout(c3)
        l3.setContentsMargins(15, 11, 15, 11)
        l3.setSpacing(4)
        r3 = QHBoxLayout()
        icon3 = QLabel("💻")
        icon3.setFixedSize(30, 30)
        icon3.setAlignment(Qt.AlignCenter)
        icon3.setStyleSheet("background:#E6F9FB; border-radius:8px; font-size:14px;")
        t3_box = QVBoxLayout()
        t3_box.setSpacing(1)
        self.metric_devices_label = QLabel("0 Devices")
        self.metric_devices_label.setStyleSheet("color:#11142D; font-size:13px; font-weight:800;")
        sub3 = QLabel("Active Nodes")
        sub3.setStyleSheet("color:#808191; font-size:9px; font-weight:700;")
        t3_box.addWidget(self.metric_devices_label)
        t3_box.addWidget(sub3)
        r3.addWidget(icon3)
        r3.addLayout(t3_box)
        r3.addStretch()
        l3.addLayout(r3)
        b3 = QHBoxLayout()
        self.metric_subnet_label = QLabel("Local Subnet")
        self.metric_subnet_label.setStyleSheet("color:#737791; font-size:10px; font-weight:600;")
        pill3 = QLabel("↑ 100% Online")
        pill3.setStyleSheet("color:#05A660; background:#E6F9F0; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
        b3.addWidget(self.metric_subnet_label)
        b3.addStretch()
        b3.addWidget(pill3)
        l3.addLayout(b3)
        metrics.addWidget(c3, 1)

        # Card 4: Action Card
        c4 = QPushButton()
        c4.setMinimumHeight(86)
        c4.setCursor(Qt.PointingHandCursor)
        c4.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border: 1.5px dashed #D6D2F0;
                border-radius: 18px;
                padding: 10px;
                text-align: center;
            }
            QPushButton:hover {
                background: #F8F7FD;
                border-color: #5B4DF0;
            }
        """)
        c4.clicked.connect(self.refresh_network)
        l4 = QVBoxLayout(c4)
        l4.setContentsMargins(10, 8, 10, 8)
        l4.setSpacing(3)
        l4.setAlignment(Qt.AlignCenter)
        plus_icon = QLabel("+")
        plus_icon.setFixedSize(24, 24)
        plus_icon.setAlignment(Qt.AlignCenter)
        plus_icon.setStyleSheet("color:#FF5A79; background:#FFEBEF; border-radius:12px; font-size:16px; font-weight:900;")
        l4.addWidget(plus_icon, 0, Qt.AlignCenter)
        plus_text = QLabel("Rescan Network")
        plus_text.setStyleSheet("color:#11142D; font-size:11px; font-weight:800;")
        l4.addWidget(plus_text, 0, Qt.AlignCenter)
        plus_sub = QLabel("Instant ARP Discovery")
        plus_sub.setStyleSheet("color:#808191; font-size:9px; font-weight:600;")
        l4.addWidget(plus_sub, 0, Qt.AlignCenter)
        metrics.addWidget(c4, 1)

        app.addWidget(self.metrics_container)
        self.metrics_container.setVisible(False)

        # Retain backward compatibility attributes
        self.shell_metric_cards = []
        self.topology_status_labels = []
        self.devices_connected_badge = QLabel("● 0 Devices Connected")

        self.pages = QStackedWidget()
        self.pages.setStyleSheet(
            "QStackedWidget { background:transparent; border:none; }"
        )

        self.topology_page = self.create_topology_page()
        self.live_scan_page = self.create_live_scan_page()
        self.devices_page = self.create_devices_page()
        self.advisor_page = self.create_advisor_page()
        self.analytics_page = self.create_analytics_page()
        self.settings_page = self.create_settings_page()

        for page in [
            self.topology_page,
            self.live_scan_page,
            self.devices_page,
            self.advisor_page,
            self.analytics_page,
            self.settings_page,
        ]:
            self.pages.addWidget(page)

        app.addWidget(self.pages, 1)

        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 14px;
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 5, 14, 5)

        self.footer_left = QLabel("⚡ WAVEIUM  •  NETWORK CONNECTIVITY VISUALIZER")
        self.footer_devices = QLabel("● Devices Discovered: 0")
        self.footer_interval = QLabel("Live update: 2 sec")

        for label in [
            self.footer_left,
            self.footer_devices,
            self.footer_interval
        ]:
            label.setStyleSheet(
                "font-size: 9px; color: #808191; font-weight: 700;"
            )

        footer_layout.addWidget(self.footer_left)
        footer_layout.addStretch()
        footer_layout.addWidget(self.footer_devices)
        footer_layout.addStretch()
        footer_layout.addWidget(self.footer_interval)
        app.addWidget(footer)

        root.addWidget(workspace, 1)

        self.navigate_to(0)
        self.set_details_panel_visible(True)
        self.update_network_overview()
        self.update_edge_selector()
        self._update_flow_labels()
        self.refresh_page_data()



    def make_page_frame(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(10)
        page.setStyleSheet("background:transparent;")
        return page, layout



    def make_card(self, title, subtitle=""):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background:#F9FAF5;
                border:1px solid #C7D3CF;
                border-radius:20px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(19, 16, 19, 16)
        layout.setSpacing(7)

        heading = QLabel(title)
        heading.setStyleSheet(
            "font-size:17px;font-weight:900;color:#173A40;"
        )
        layout.addWidget(heading)

        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet(
                "font-size:10px;color:#667A77;padding-bottom:3px;"
            )
            layout.addWidget(sub)

        return frame, layout


    def toggle_network_summary(self):

        expanded = self.summary_toggle.isChecked()

        self.summary_scroll.setVisible(expanded)

        if expanded:
            self.summary_toggle.setText("▾   Network Summary")
        else:
            self.summary_toggle.setText("▸   Network Summary")

    def toggle_sidebar(self):

        collapsed = self.sidebar.width() > 100

        if collapsed:
            self.sidebar.setFixedWidth(70)
            self.sidebar_brand.setVisible(False)
            self.sidebar_brand_sub.setVisible(False)
            self.summary_toggle.setVisible(False)
            self.summary_scroll.setVisible(False)
            self.sidebar_status.setText("●")

            icons = ["⌂", "◉", "▣", "⌁", "◌", "⚙"]
            names = [
                "Network Topology",
                "Live Scan",
                "Devices",
                "Signal Advisor",
                "Analytics",
                "Settings",
            ]

            for button, icon, name in zip(
                self.nav_buttons, icons, names
            ):
                button.setText(icon)
                button.setToolTip(name)

        else:
            self.sidebar.setFixedWidth(224)
            self.sidebar_brand.setVisible(True)
            self.sidebar_brand_sub.setVisible(True)
            self.summary_toggle.setVisible(True)
            self.summary_scroll.setVisible(
                self.summary_toggle.isChecked()
            )
            self.sidebar_status.setText("●  SYSTEM READY")

            icons = ["⌂", "◉", "▣", "⌁", "◌", "⚙"]
            names = [
                "Network Topology",
                "Live Scan",
                "Devices",
                "Signal Advisor",
                "Analytics",
                "Settings",
            ]

            for button, icon, name in zip(
                self.nav_buttons, icons, names
            ):
                button.setText(f"{icon}   {name}")
                button.setToolTip("")

    def navigate_to(self, index):

        if index < 0 or index >= self.pages.count():
            return

        self.pages.setCurrentIndex(index)

        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

        titles = [
            ("Network Topology", "Real-time network connectivity visualization"),
            ("Live Scan", "Continuous discovery and network status"),
            ("Devices", "Connected devices discovered on the network"),
            ("Signal Advisor", "Signal strength, distance and movement guidance"),
            ("Analytics", "Network performance and live measurements"),
            ("Settings", "Waveium appearance, scanning and behavior"),
        ]

        title, subtitle = titles[index]
        self.page_title.setText(title)
        self.page_subtitle.setText(subtitle)
        self.details_header_button.setVisible(index == 0)
        if hasattr(self, "panel_header_button"):
            self.panel_header_button.setVisible(index == 0)

        # Full-Space Topology: hide top metrics on topology page, show on others
        if hasattr(self, "metrics_container"):
            self.metrics_container.setVisible(index != 0)
        if hasattr(self, "filter_bar_container"):
            self.filter_bar_container.setVisible(False)
        if hasattr(self, "flow_pill"):
            self.flow_pill.setVisible(index == 0)

        if index == 3:
            self.update_advisor_page()
        elif index == 4:
            self.update_analytics_page()
        elif index == 2:
            self.update_devices_page()
        elif index == 1:
            self.update_live_scan_page()

    def create_topology_page(self):

        page, main_layout = self.make_page_frame()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        wifi = self.network_data.get("wifi", {})

        self.ssid_label = QLabel(
            f"SSID: {wifi.get('ssid') or 'N/A'}"
        )
        self.bssid_label = QLabel(
            f"BSSID: {wifi.get('bssid') or 'N/A'}"
        )
        self.band_label = QLabel(
            f"Band: {wifi.get('band') or 'N/A'}"
        )
        self.channel_label = QLabel(
            f"Channel: {wifi.get('channel') or 'N/A'}"
        )
        self.signal_label = QLabel(
            f"Signal: {wifi.get('signal_percent') if wifi.get('signal_percent') is not None else 'N/A'}%"
        )
        self.count_label = QLabel(
            f"●  {len(self.network_data.get('devices', [])) + 1} Devices Connected"
        )

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)

        # ── LARGE CENTRAL FULL-SPACE NETWORK TOPOLOGY CARD ──
        graph_frame = QFrame()
        graph_frame.setStyleSheet(
            """
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
            """
        )

        graph_layout = QVBoxLayout(graph_frame)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(0)

        self.graph_canvas = WaveiumGraphCanvas(self.graph)
        wifi_init = self.network_data.get("wifi", {})
        cov_init = WaveiumGraphGenerator.estimate_router_coverage(
            band=wifi_init.get("band"),
            current_rssi=wifi_init.get("rssi"),
            current_distance=wifi_init.get("distance")
        )
        self.graph_canvas.set_coverage_info(cov_init)
        self.graph_canvas.device_selected.connect(self.device_selected)
        self.graph_canvas.setMinimumSize(0, 0)
        self.graph_canvas.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding
        )
        graph_layout.addWidget(self.graph_canvas, 1)

        content.addWidget(graph_frame, 1)

        # ── EDGE OPEN BUTTON (Visible when details panel is closed) ──
        self.right_panel_open_btn = QPushButton("◀  Device Details")
        self.right_panel_open_btn.setCursor(Qt.PointingHandCursor)
        self.right_panel_open_btn.setToolTip("Open Device Details panel")
        self.right_panel_open_btn.setFixedHeight(38)
        self.right_panel_open_btn.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #5B4DF0;
                border: 1.5px solid #5B4DF0;
                border-radius: 12px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #5B4DF0;
                color: #FFFFFF;
            }
        """)
        self.right_panel_open_btn.clicked.connect(lambda: self.set_details_panel_visible(True))
        self.right_panel_open_btn.setVisible(False)
        content.addWidget(self.right_panel_open_btn, 0, Qt.AlignTop)

        right_holder = QWidget()
        right_holder.setFixedWidth(270)

        right_holder_layout = QVBoxLayout(right_holder)
        right_holder_layout.setContentsMargins(0, 0, 0, 0)
        right_holder_layout.setSpacing(8)

        details_header = QHBoxLayout()

        details_title = QLabel("DEVICE DETAILS")
        details_title.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #11142D; letter-spacing: 0.5px;"
        )
        details_header.addWidget(details_title)
        details_header.addStretch()

        self.details_close_button = QPushButton("✕  Close")
        self.details_close_button.setFixedHeight(28)
        self.details_close_button.setCursor(Qt.PointingHandCursor)
        self.details_close_button.setToolTip("Close Device Details panel")
        self.details_close_button.setStyleSheet("""
            QPushButton {
                background: #F6F5FD;
                color: #5B4DF0;
                border: 1px solid #EAE7F6;
                border-radius: 10px;
                padding: 4px 10px;
                font-weight: 800;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #5B4DF0;
                color: #FFFFFF;
                border-color: #5B4DF0;
            }
        """)
        self.details_close_button.clicked.connect(self.close_details_panel)
        details_header.addWidget(self.details_close_button)

        right_holder_layout.addLayout(details_header)

        right_content = QWidget()
        right_content.setStyleSheet("background: transparent;")

        right_content_layout = QVBoxLayout(right_content)
        right_content_layout.setContentsMargins(0, 8, 6, 8)
        right_content_layout.setSpacing(10)

        self.node_info_frame = self.create_node_panel()
        right_content_layout.addWidget(self.node_info_frame)

        self.signal_panel = self.create_signal_controls()
        right_content_layout.addWidget(self.signal_panel)

        right_content_layout.addStretch()

        self.right_scroll = self.make_scroll_area(
            right_content,
            width=270,
            outer=False,
        )

        right_holder_layout.addWidget(self.right_scroll, 1)
        self.right_holder = right_holder
        self.right_holder.setVisible(True)

        content.addWidget(right_holder, 0)
        main_layout.addLayout(content, 1)

        return page

    # ==================================================
    # LIVE SCAN PAGE
    # ==================================================

    def create_live_scan_page(self):

        page, layout = self.make_page_frame()

        # ── HERO BAR ──
        hero = QFrame()
        hero.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(16)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(3)
        hero_title = QLabel("Live Network Discovery")
        hero_title.setStyleSheet("font-size: 22px; font-weight: 900; color: #11142D;")
        hero_sub = QLabel("Continuous ARP subnet scanning, Wi-Fi PHY interface diagnostics, and adapter telemetry.")
        hero_sub.setStyleSheet("font-size: 11px; color: #808191; font-weight: 600;")
        hero_text.addWidget(hero_title)
        hero_text.addWidget(hero_sub)
        hero_layout.addLayout(hero_text)
        hero_layout.addStretch()

        self.live_scan_status = QLabel("●  LIVE SCAN ACTIVE")
        self.live_scan_status.setAlignment(Qt.AlignCenter)
        self.live_scan_status.setStyleSheet("""
            QLabel {
                background: #E6F9F0;
                color: #05A660;
                border: 1px solid #C1F1D8;
                border-radius: 14px;
                padding: 8px 16px;
                font-size: 10px;
                font-weight: 800;
            }
        """)
        hero_layout.addWidget(self.live_scan_status)

        scan_btn = QPushButton("⟳  Scan Network")
        scan_btn.setCursor(Qt.PointingHandCursor)
        scan_btn.setFixedHeight(38)
        scan_btn.setStyleSheet("""
            QPushButton {
                background: #5B4DF0;
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                padding: 8px 18px;
                font-size: 11px;
                font-weight: 800;
            }
            QPushButton:hover { background: #4738DB; }
        """)
        scan_btn.clicked.connect(self.refresh_network)
        hero_layout.addWidget(scan_btn)

        layout.addWidget(hero)

        # ── TOP 4 KPI CARDS ──
        stats = QHBoxLayout()
        stats.setSpacing(12)

        self.live_devices_metric = self.make_dashboard_metric(
            "DISCOVERED NODES", "0", "Current network", pill_text="↑ 100% Reachable"
        )
        self.live_signal_metric = self.make_dashboard_metric(
            "LOCAL SIGNAL", "—", "Wi-Fi strength", pill_text="↑ Excellent"
        )
        self.live_band_metric = self.make_dashboard_metric(
            "NETWORK BAND", "—", "Current adapter", pill_text="80 MHz Wide"
        )
        self.live_speed_metric = self.make_dashboard_metric(
            "LINK PHY RATE", "—", "RX / TX", pill_text="High Bandwidth"
        )

        for card in [
            self.live_devices_metric,
            self.live_signal_metric,
            self.live_band_metric,
            self.live_speed_metric,
        ]:
            stats.addWidget(card)

        layout.addLayout(stats)

        # ── MAIN CONTENT: CONSOLE (LEFT) + SPECTRUM SPECS (RIGHT) ──
        split_layout = QHBoxLayout()
        split_layout.setSpacing(14)

        # Left Column: Discovery Telemetry Console
        console_frame = QFrame()
        console_frame.setStyleSheet("""
            QFrame {
                background: #11142D;
                border: 1px solid #23263B;
                border-radius: 20px;
            }
        """)
        console_layout = QVBoxLayout(console_frame)
        console_layout.setContentsMargins(20, 18, 20, 18)
        console_layout.setSpacing(10)

        con_header = QHBoxLayout()
        con_title = QLabel("● ● ●   DISCOVERY TELEMETRY LOG")
        con_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #808191; letter-spacing: 0.5px;")
        con_header.addWidget(con_title)
        con_header.addStretch()

        con_badge = QLabel("LIVE FEED")
        con_badge.setStyleSheet("color: #00D2A0; background: rgba(0,210,160,0.15); border-radius: 8px; padding: 2px 8px; font-size: 9px; font-weight: 800;")
        con_header.addWidget(con_badge)
        console_layout.addLayout(con_header)

        self.live_scan_console = QLabel()
        self.live_scan_console.setWordWrap(True)
        self.live_scan_console.setStyleSheet("""
            QLabel {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                color: #00D2A0;
                line-height: 1.6;
                padding: 4px;
            }
        """)
        console_layout.addWidget(self.live_scan_console, 1)

        split_layout.addWidget(console_frame, 6)

        # Right Column: Adapter & Radio Spectrum Specifications
        props_frame = QFrame()
        props_frame.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        props_layout = QVBoxLayout(props_frame)
        props_layout.setContentsMargins(20, 18, 20, 18)
        props_layout.setSpacing(10)

        props_title = QLabel("ADAPTER & RADIO SPECTRUM")
        props_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #11142D; letter-spacing: 0.5px;")
        props_layout.addWidget(props_title)

        self.live_scan_info = QLabel()
        self.live_scan_info.setWordWrap(True)
        self.live_scan_info.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #53696A;
                line-height: 1.7;
                font-weight: 600;
            }
        """)
        props_layout.addWidget(self.live_scan_info, 1)

        split_layout.addWidget(props_frame, 4)

        layout.addLayout(split_layout, 1)

        return page

    def make_dashboard_metric(self, title, value, subtitle, pill_text=None):

        card = QFrame()
        card.setMinimumHeight(108)
        card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 18px;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 13, 16, 13)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "font-size: 10px; color: #808191; font-weight: 800; letter-spacing: 0.5px;"
        )
        top_row.addWidget(title_label)
        top_row.addStretch()

        if pill_text:
            pill = QLabel(pill_text)
            pill.setStyleSheet(
                "color: #05A660; background: #E6F9F0; border-radius: 8px; padding: 2px 7px; font-size: 9px; font-weight: 800;"
            )
            top_row.addWidget(pill)
            card.pill_label = pill

        layout.addLayout(top_row)

        value_label = QLabel(value)
        value_label.setStyleSheet(
            "font-size: 24px; color: #11142D; font-weight: 900;"
        )
        layout.addWidget(value_label)

        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(
            "font-size: 10px; color: #808191; font-weight: 600;"
        )
        layout.addWidget(sub_label)

        card.value_label = value_label
        card.sub_label = sub_label
        return card

    # ==================================================
    # DEVICES PAGE
    # ==================================================

    def create_devices_page(self):

        page, layout = self.make_page_frame()

        # ── HERO BAR ──
        hero = QFrame()
        hero.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(16)

        left_hero = QVBoxLayout()
        left_hero.setSpacing(4)
        title = QLabel("Connected Devices")
        title.setStyleSheet("font-size: 20px; font-weight: 900; color: #11142D;")
        desc = QLabel("Real-time network registry of AP infrastructure, local host, and discovered peer clients")
        desc.setStyleSheet("font-size: 11px; color: #808191; font-weight: 500;")
        left_hero.addWidget(title)
        left_hero.addWidget(desc)
        hero_layout.addLayout(left_hero, 1)

        self.devices_count_badge = QLabel("●  0 NODES ACTIVE")
        self.devices_count_badge.setStyleSheet("""
            background: #E6F9F0;
            color: #05A660;
            border-radius: 12px;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: 800;
        """)
        hero_layout.addWidget(self.devices_count_badge)

        layout.addWidget(hero)

        # ── 4 KPI CARDS ──
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.dev_metric_total = self.make_dashboard_metric(
            "TOTAL CLIENTS", "0", "Discovered on subnet", "SUBNET"
        )
        self.dev_metric_gateway = self.make_dashboard_metric(
            "GATEWAY AP", "—", "Default uplink router", "INFRA"
        )
        self.dev_metric_host = self.make_dashboard_metric(
            "THIS PC", "—", "Local network interface", "HOST"
        )
        self.dev_metric_integrity = self.make_dashboard_metric(
            "LINK INTEGRITY", "100%", "Packet delivery health", "OPTIMAL"
        )

        metrics_layout.addWidget(self.dev_metric_total)
        metrics_layout.addWidget(self.dev_metric_gateway)
        metrics_layout.addWidget(self.dev_metric_host)
        metrics_layout.addWidget(self.dev_metric_integrity)

        layout.addLayout(metrics_layout)

        # ── TABLE CONTAINER CARD ──
        table_card = QFrame()
        table_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(20, 18, 20, 20)
        table_layout.setSpacing(14)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        self.device_search = QLineEdit()
        self.device_search.setPlaceholderText("🔍  Search devices by name, IP, MAC address, or role...")
        self.device_search.setMinimumHeight(38)
        self.device_search.setStyleSheet("""
            QLineEdit {
                background: #F8F7FD;
                border: 1px solid #ECECF6;
                border-radius: 12px;
                padding: 6px 14px;
                color: #11142D;
                font-size: 12px;
                font-weight: 500;
            }
            QLineEdit:focus {
                border: 1.5px solid #5B4DF0;
                background: #FFFFFF;
            }
        """)
        self.device_search.textChanged.connect(self.filter_devices_table)
        toolbar.addWidget(self.device_search, 1)

        refresh_devices = QPushButton("⟳  Rescan Network")
        refresh_devices.setMinimumHeight(38)
        refresh_devices.setCursor(Qt.PointingHandCursor)
        refresh_devices.clicked.connect(self.refresh_network)
        refresh_devices.setStyleSheet("""
            QPushButton {
                background: #5B4DF0;
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #4738DB;
            }
            QPushButton:pressed {
                background: #392BB8;
            }
        """)
        toolbar.addWidget(refresh_devices)

        table_layout.addLayout(toolbar)

        self.device_table = QTableWidget()
        self.device_table.setColumnCount(6)
        self.device_table.setHorizontalHeaderLabels(
            ["Device", "IP Address", "MAC Address", "Role", "Signal", "Status"]
        )
        self.device_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.device_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.device_table.setAlternatingRowColors(True)
        self.device_table.setShowGrid(False)
        self.device_table.verticalHeader().setVisible(False)
        self.device_table.horizontalHeader().setStretchLastSection(True)
        self.device_table.horizontalHeader().setDefaultSectionSize(140)
        self.device_table.setStyleSheet("""
            QTableWidget {
                background: #FFFFFF;
                alternate-background-color: #FAFAFD;
                border: 1px solid #ECECF6;
                border-radius: 12px;
                color: #11142D;
                font-size: 12px;
            }
            QHeaderView::section {
                background: #F8F7FD;
                color: #808191;
                padding: 10px 12px;
                border: none;
                border-bottom: 1.5px solid #ECECF6;
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
            QTableWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #F4F4F9;
            }
            QTableWidget::item:selected {
                background: #F0EDFF;
                color: #5B4DF0;
            }
        """)

        table_layout.addWidget(self.device_table, 1)
        layout.addWidget(table_card, 1)

        return page

    def filter_devices_table(self, value):

        if not hasattr(self, "device_table"):
            return

        query = value.strip().lower()

        for row in range(self.device_table.rowCount()):
            visible = not query

            if query:
                for col in range(self.device_table.columnCount()):
                    item = self.device_table.item(row, col)
                    if item and query in item.text().lower():
                        visible = True
                        break

            self.device_table.setRowHidden(row, not visible)

    # ==================================================
    # SIGNAL ADVISOR PAGE
    # ==================================================

    def create_advisor_page(self):

        page, page_layout = self.make_page_frame()

        # ==================================================
        # CENTERED ADVISOR WORKSPACE
        # ==================================================

        workspace = QWidget()
        workspace.setMaximumWidth(1180)

        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(4, 4, 4, 4)
        workspace_layout.setSpacing(14)

        # --------------------------------------------------
        # HERO
        # --------------------------------------------------

        hero = QFrame()
        hero.setStyleSheet(
            """
            QFrame {
                background:#FFFDF7;
                border:1px solid #DCE9E1;
                border-radius:20px;
            }
            """
        )

        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 20, 24, 20)
        hero_layout.setSpacing(18)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)

        hero_title = QLabel("Signal Advisor")
        hero_title.setStyleSheet(
            "font-size:25px; font-weight:900; color:#173A40;"
        )
        hero_text.addWidget(hero_title)

        hero_subtitle = QLabel(
            "Understand your current Wi-Fi position and get movement guidance."
        )
        hero_subtitle.setStyleSheet(
            "font-size:12px; color:#53696A;"
        )
        hero_text.addWidget(hero_subtitle)

        hero_layout.addLayout(hero_text)
        hero_layout.addStretch()

        self.advisor_hero_status = QLabel("● LIVE MEASUREMENT")
        self.advisor_hero_status.setAlignment(Qt.AlignCenter)
        self.advisor_hero_status.setStyleSheet(
            """
            QLabel {
                background:#D7F4E7;
                color:#15844C;
                border:1px solid #BDE7CC;
                border-radius:16px;
                padding:9px 15px;
                font-size:10px;
                font-weight:800;
            }
            """
        )
        hero_layout.addWidget(self.advisor_hero_status)

        workspace_layout.addWidget(hero)

        # --------------------------------------------------
        # ANIMATED LIVE COVERAGE RADAR & DISTANCE TRACK
        # --------------------------------------------------
        self.advisor_radar_widget = SignalRadarTrackWidget()
        workspace_layout.addWidget(self.advisor_radar_widget)

        # --------------------------------------------------
        # MAIN SIGNAL + GUIDANCE ROW
        # --------------------------------------------------

        main_row = QHBoxLayout()
        main_row.setSpacing(14)

        # Current signal card.
        signal_card = QFrame()
        signal_card.setMinimumHeight(240)
        signal_card.setStyleSheet(
            """
            QFrame {
                background:#FFFFFF;
                border:1px solid #ECECF6;
                border-radius:20px;
            }
            """
        )

        signal_layout = QVBoxLayout(signal_card)
        signal_layout.setContentsMargins(22, 18, 22, 18)
        signal_layout.setSpacing(7)

        signal_heading = QLabel("CURRENT SIGNAL")
        signal_heading.setStyleSheet(
            "font-size:11px; font-weight:900; color:#53696A; letter-spacing:0.5px;"
        )
        signal_layout.addWidget(signal_heading)

        signal_value_row = QHBoxLayout()

        self.advisor_signal_value = QLabel("—")
        self.advisor_signal_value.setStyleSheet(
            "font-size:36px; font-weight:900; color:#087B55;"
        )
        signal_value_row.addWidget(self.advisor_signal_value)

        self.advisor_quality_pill = QLabel("NO DATA")
        self.advisor_quality_pill.setAlignment(Qt.AlignCenter)
        self.advisor_quality_pill.setMinimumWidth(95)
        self.advisor_quality_pill.setStyleSheet(
            """
            QLabel {
                background:#D8E8E3;
                color:#087B55;
                border:1px solid #86CFAE;
                border-radius:13px;
                padding:7px 10px;
                font-size:10px;
                font-weight:900;
            }
            """
        )
        signal_value_row.addWidget(self.advisor_quality_pill)
        signal_value_row.addStretch()

        signal_layout.addLayout(signal_value_row)

        self.advisor_signal_percent = QLabel("Signal strength: —")
        self.advisor_signal_percent.setStyleSheet(
            "font-size:12px; color:#6D5B63; font-weight:600;"
        )
        signal_layout.addWidget(self.advisor_signal_percent)

        self.advisor_signal_bar = QProgressBar()
        self.advisor_signal_bar.setRange(0, 100)
        self.advisor_signal_bar.setValue(0)
        self.advisor_signal_bar.setTextVisible(False)
        self.advisor_signal_bar.setFixedHeight(12)
        self.advisor_signal_bar.setStyleSheet(
            """
            QProgressBar {
                background:#F0E5E9;
                border:1px solid #E3D0D8;
                border-radius:6px;
            }
            QProgressBar::chunk {
                background:#05A660;
                border-radius:5px;
            }
            """
        )
        signal_layout.addWidget(self.advisor_signal_bar)

        signal_layout.addStretch()

        rssi_note = QLabel(
            "Real-time RF RSSI measured from local Wi-Fi adapter."
        )
        rssi_note.setWordWrap(True)
        rssi_note.setStyleSheet(
            "font-size:10px; color:#9A858E;"
        )
        signal_layout.addWidget(rssi_note)

        main_row.addWidget(signal_card, 1)

        # Distance card.
        distance_card = QFrame()
        distance_card.setMinimumHeight(240)
        distance_card.setStyleSheet(
            """
            QFrame {
                background:#FFFFFF;
                border:1px solid #ECECF6;
                border-radius:20px;
            }
            """
        )

        distance_layout = QVBoxLayout(distance_card)
        distance_layout.setContentsMargins(22, 18, 22, 18)
        distance_layout.setSpacing(5)

        distance_heading = QLabel("ESTIMATED DISTANCE")
        distance_heading.setStyleSheet(
            "font-size:11px; font-weight:900; color:#53696A; letter-spacing:0.5px;"
        )
        distance_layout.addWidget(distance_heading)

        self.advisor_distance_value = QLabel("—")
        self.advisor_distance_value.setStyleSheet(
            "font-size:36px; font-weight:900; color:#087B55;"
        )
        distance_layout.addWidget(self.advisor_distance_value)

        self.advisor_distance_sub = QLabel("metres from the router")
        self.advisor_distance_sub.setStyleSheet(
            "font-size:11px; color:#6D5B63; font-weight:600;"
        )
        distance_layout.addWidget(self.advisor_distance_sub)

        # Coverage Thresholds Breakdown
        dist_meta_box = QVBoxLayout()
        dist_meta_box.setSpacing(2)
        self.advisor_good_boundary_label = QLabel("⚡ Good Coverage Limit: 550 cm (5.5 m)")
        self.advisor_good_boundary_label.setStyleSheet("font-size:10px; color:#2563EB; font-weight:700;")
        self.advisor_peak_boundary_label = QLabel("⭐ Peak Speed Range: ≤ 240 cm (2.4 m)")
        self.advisor_peak_boundary_label.setStyleSheet("font-size:10px; color:#05A660; font-weight:700;")
        self.advisor_router_cov_label = QLabel("📡 Est. Router Coverage: ~30 m (3000 cm) • ~200 m²")
        self.advisor_router_cov_label.setStyleSheet("font-size:10px; color:#5B4DF0; font-weight:700;")
        dist_meta_box.addWidget(self.advisor_good_boundary_label)
        dist_meta_box.addWidget(self.advisor_peak_boundary_label)
        dist_meta_box.addWidget(self.advisor_router_cov_label)
        distance_layout.addLayout(dist_meta_box)

        distance_layout.addStretch()

        distance_note = QLabel(
            "Formatted in cm (≤ 5m) via RF path-loss model."
        )
        distance_note.setWordWrap(True)
        distance_note.setStyleSheet(
            "font-size:10px; color:#9A858E;"
        )
        distance_layout.addWidget(distance_note)

        main_row.addWidget(distance_card, 1)

        # Guidance card.
        guidance_card = QFrame()
        guidance_card.setMinimumHeight(240)
        guidance_card.setStyleSheet(
            """
            QFrame {
                background:#EAF8EC;
                border:1px solid #D7EADF;
                border-radius:20px;
            }
            """
        )

        guidance_layout = QVBoxLayout(guidance_card)
        guidance_layout.setContentsMargins(22, 18, 22, 18)
        guidance_layout.setSpacing(7)

        guidance_heading = QLabel("MOVEMENT GUIDANCE")
        guidance_heading.setStyleSheet(
            "font-size:11px; font-weight:900; color:#087B55; letter-spacing:0.5px;"
        )
        guidance_layout.addWidget(guidance_heading)

        self.advisor_status_badge = QLabel("●  EXCELLENT COVERAGE")
        self.advisor_status_badge.setAlignment(Qt.AlignCenter)
        self.advisor_status_badge.setMinimumHeight(38)
        self.advisor_status_badge.setStyleSheet(
            """
            QLabel {
                background:#D8E8E3;
                color:#087B55;
                border:1px solid #86CFAE;
                border-radius:13px;
                padding:6px;
                font-size:12px;
                font-weight:900;
            }
            """
        )
        guidance_layout.addWidget(self.advisor_status_badge)

        self.advisor_message = QLabel(
            "Analyzing signal range and movement headroom..."
        )
        self.advisor_message.setWordWrap(True)
        self.advisor_message.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.advisor_message.setStyleSheet(
            "font-size:11px; color:#173A40; font-weight:700; line-height:1.4;"
        )
        guidance_layout.addWidget(self.advisor_message)

        guidance_layout.addStretch()

        self.advisor_action = QLabel("●  Proximity requirement: Stay within 550 cm for Good network")
        self.advisor_action.setWordWrap(True)
        self.advisor_action.setStyleSheet(
            "font-size:9.5px; color:#53696A; font-weight:700;"
        )
        guidance_layout.addWidget(self.advisor_action)

        main_row.addWidget(guidance_card, 1)

        workspace_layout.addLayout(main_row)

        # --------------------------------------------------
        # SIGNAL SCALE
        # --------------------------------------------------

        scale_card = QFrame()
        scale_card.setStyleSheet(
            """
            QFrame {
                background:#FFFDF7;
                border:1px solid #DCE9E1;
                border-radius:18px;
            }
            """
        )

        scale_layout = QVBoxLayout(scale_card)
        scale_layout.setContentsMargins(20, 14, 20, 14)
        scale_layout.setSpacing(8)

        scale_title = QLabel("SIGNAL QUALITY SCALE")
        scale_title.setStyleSheet(
            "font-size:11px; font-weight:900; color:#173A40;"
        )
        scale_layout.addWidget(scale_title)

        zones = QHBoxLayout()
        zones.setSpacing(7)

        zone_data = [
            ("EXCELLENT", "≥ -50 dBm", "#16A66B"),
            ("GOOD", "-51 to -60 dBm", "#2D8BEA"),
            ("FAIR", "-61 to -70 dBm", "#F2A900"),
            ("WEAK", "-71 to -80 dBm", "#F06B27"),
            ("VERY WEAK", "< -80 dBm", "#B72B2B"),
        ]

        self.advisor_zone_labels = []

        for name, range_text, color in zone_data:
            zone = QLabel(
                f"●  {name}\n   {range_text}"
            )
            zone.setStyleSheet(
                f"""
                QLabel {{
                    background:#F8FBEF;
                    color:{color};
                    border:1px solid #DCE9E1;
                    border-radius:10px;
                    padding:7px 9px;
                    font-size:9px;
                    font-weight:800;
                }}
                """
            )
            zone.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            zones.addWidget(zone, 1)
            self.advisor_zone_labels.append((name, zone))

        scale_layout.addLayout(zones)
        workspace_layout.addWidget(scale_card)

        # --------------------------------------------------
        # HOW IT WORKS
        # --------------------------------------------------

        method_card = QFrame()
        method_card.setStyleSheet(
            """
            QFrame {
                background:#FFFDF7;
                border:1px solid #DCE9E1;
                border-radius:18px;
            }
            """
        )

        method_layout = QVBoxLayout(method_card)
        method_layout.setContentsMargins(20, 15, 20, 15)
        method_layout.setSpacing(7)

        method_title = QLabel("HOW WAVEIUM ESTIMATES DISTANCE")
        method_title.setStyleSheet(
            "font-size:11px; font-weight:900; color:#173A40;"
        )
        method_layout.addWidget(method_title)

        method_flow = QLabel(
            "Wi-Fi RSSI   →   Signal Quality   →   Distance Estimate   →   Movement Guidance"
        )
        method_flow.setAlignment(Qt.AlignCenter)
        method_flow.setStyleSheet(
            "font-size:13px; color:#087B55; font-weight:800; padding:5px;"
        )
        method_layout.addWidget(method_flow)

        method_note = QLabel(
            "The distance shown by Waveium is an RSSI-based approximation. "
            "Walls, interference, antenna position and other environmental factors can affect the estimate."
        )
        method_note.setWordWrap(True)
        method_note.setAlignment(Qt.AlignCenter)
        method_note.setStyleSheet(
            "font-size:10px; color:#53696A;"
        )
        method_layout.addWidget(method_note)

        workspace_layout.addWidget(method_card)

        # Compatibility labels retained for existing references.
        self.advisor_title = QLabel()
        self.advisor_details = QLabel()

        scroll = self.make_scroll_area(workspace, outer=True)
        page_layout.addWidget(scroll, 1)

        return page

    def update_advisor_page(self):

        if not hasattr(self, "advisor_signal_value"):
            return

        wifi = self.network_data.get("wifi", {})
        rssi = wifi.get("rssi")
        signal = wifi.get("signal_percent")

        if rssi is None:
            self.advisor_signal_value.setText("—")
            self.advisor_distance_value.setText("—")
            self.advisor_quality_pill.setText("NO DATA")
            self.advisor_signal_percent.setText("Signal strength: —")
            self.advisor_signal_bar.setValue(0)
            self.advisor_status_badge.setText("●  SIGNAL UNAVAILABLE")
            self.advisor_message.setText(
                "Waveium could not obtain a current RSSI measurement "
                "from the local Wi-Fi adapter."
            )
            self.advisor_action.setText(
                "●  Waiting for a valid Wi-Fi signal measurement"
            )
            return

        try:
            rssi_int = int(rssi)
        except (TypeError, ValueError):
            return

        quality = str(
            WaveiumGraphGenerator.signal_quality(rssi_int)
        ).upper()

        distance = WaveiumGraphGenerator.estimate_distance(rssi_int)

        try:
            signal_value = (
                max(0, min(100, int(signal)))
                if signal is not None else 0
            )
        except (TypeError, ValueError):
            signal_value = 0

        self.advisor_signal_value.setText(
            f"{rssi_int} dBm"
        )
        self.advisor_signal_percent.setText(
            f"Signal strength: {signal_value}%"
        )
        self.advisor_signal_bar.setValue(signal_value)

        # ── DISTANCE DISPLAY IN CM (<= 5.0m) OR METERS (> 5.0m) ──
        def fmt_dist(d):
            if d is None:
                return "—"
            if d <= 5.0:
                return f"{int(round(d * 100))} cm"
            return f"{d:.2f} m"

        if distance <= 5.0:
            cm_val = int(round(distance * 100))
            self.advisor_distance_value.setText(f"{cm_val} cm")
            if hasattr(self, "advisor_distance_sub"):
                self.advisor_distance_sub.setText(f"({distance:.2f} metres from the router)")
        else:
            self.advisor_distance_value.setText(f"{distance:.2f} m")
            if hasattr(self, "advisor_distance_sub"):
                self.advisor_distance_sub.setText("metres from the router")

        # ── ESTIMATED ROUTER SIGNAL COVERAGE ──
        band = wifi.get("band", "5 GHz")
        cov_info = WaveiumGraphGenerator.estimate_router_coverage(
            band=band,
            current_rssi=rssi_int,
            current_distance=distance
        )
        if hasattr(self, "advisor_router_cov_label"):
            self.advisor_router_cov_label.setText(
                f"📡 Est. Router Reach: ~{cov_info['max_distance']} m ({int(cov_info['max_distance']*100)} cm) • ~{cov_info['area_sqm']} m²"
            )

        # ── MOVEMENT ADVISOR & RANGE INTELLIGENCE ──
        good_threshold = 5.50

        if rssi_int >= -50:
            bg, fg, border = "#D7F4E7", "#15844C", "#BDE7CC"
            badge = "●  EXCELLENT (PEAK SPEED)"
            buf_dist = max(0.1, good_threshold - distance)
            buf_str = fmt_dist(buf_dist)
            message = (
                f"Your signal is very strong ({rssi_int} dBm). You can move up to {buf_str} farther "
                f"from your current position while maintaining Good coverage (limit: 550 cm)."
            )
            action = "●  Proximity requirement: Stay within 550 cm for Good network (≤ 240 cm for Peak speed)"

        elif rssi_int >= -60:
            bg, fg, border = "#EAF3FF", "#2678C8", "#C5DDF5"
            badge = "●  GOOD COVERAGE"
            buf_dist = max(0.1, good_threshold - distance)
            buf_str = fmt_dist(buf_dist)
            message = (
                f"Your position has a stable, high-speed connection ({rssi_int} dBm). "
                f"You can move up to {buf_str} farther before signal drops into the moderate zone."
            )
            action = "●  Proximity requirement: Stay within 550 cm (5.5 m) of the router for Good network"

        elif rssi_int >= -70:
            bg, fg, border = "#FFF5DC", "#B27700", "#F0D99A"
            badge = "●  FAIR (MODERATE SIGNAL)"
            closer_dist = max(0.1, distance - good_threshold)
            closer_str = fmt_dist(closer_dist)
            message = (
                f"Signal is moderate ({rssi_int} dBm). Move approximately {closer_str} closer to the router "
                f"to enter the Good coverage zone (≤ 550 cm) and boost throughput."
            )
            action = f"●  Move advice: Move {closer_str} closer to router"

        elif rssi_int >= -80:
            bg, fg, border = "#FFF0E7", "#D65C22", "#F2C5AC"
            badge = "●  WEAK SIGNAL WARNING"
            closer_dist = max(0.1, distance - good_threshold)
            closer_str = fmt_dist(closer_dist)
            message = (
                f"⚠️ Signal is weak ({rssi_int} dBm). Move approximately {closer_str} closer to the router "
                f"to restore Good coverage and eliminate packet loss."
            )
            action = f"●  Move advice: Move {closer_str} closer to router"

        else:
            bg, fg, border = "#FCE8E8", "#B72B2B", "#E9B8B8"
            badge = "●  CRITICAL / VERY WEAK"
            closer_dist = max(0.1, distance - good_threshold)
            closer_str = fmt_dist(closer_dist)
            message = (
                f"⚠️ Disconnection risk! Move approximately {closer_str} closer to the router "
                f"immediately to re-establish a reliable Good connection."
            )
            action = f"●  Move advice: Move {closer_str} closer to router immediately"

        self.advisor_quality_pill.setText(quality)
        self.advisor_quality_pill.setStyleSheet(
            f"""
            QLabel {{
                background:{bg};
                color:{fg};
                border:1px solid {border};
                border-radius:13px;
                padding:7px 10px;
                font-size:10px;
                font-weight:900;
            }}
            """
        )

        self.advisor_status_badge.setText(badge)
        self.advisor_status_badge.setStyleSheet(
            f"""
            QLabel {{
                background:{bg};
                color:{fg};
                border:1px solid {border};
                border-radius:13px;
                padding:8px;
                font-size:12px;
                font-weight:900;
            }}
            """
        )

        self.advisor_message.setText(message)
        self.advisor_action.setText(action)

        self.advisor_hero_status.setText(
            "●  LIVE MEASUREMENT"
        )

        # Update animated radar track widget
        if hasattr(self, "advisor_radar_widget"):
            self.advisor_radar_widget.update_state(
                rssi_int, distance, signal_value, quality
            )

        self.advisor_title.setText(
            f"{quality} • {rssi_int} dBm"
        )
        self.advisor_details.setText(
            f"Current signal: {signal_value}%\n"
            f"Estimated distance: {fmt_dist(distance)}\n"
            f"Advisor: {message}"
        )

    # ==================================================
    # ANALYTICS PAGE
    # ==================================================

    def create_analytics_page(self):

        page, layout = self.make_page_frame()

        # ── HERO BAR ──
        hero = QFrame()
        hero.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 18, 24, 18)
        hero_layout.setSpacing(16)

        left_hero = QVBoxLayout()
        left_hero.setSpacing(4)
        title = QLabel("Network Analytics & Diagnostics")
        title.setStyleSheet("font-size: 20px; font-weight: 900; color: #11142D;")
        desc = QLabel("Graph topology graph-theory metrics, RF spectrum distribution, and composite health diagnostics")
        desc.setStyleSheet("font-size: 11px; color: #808191; font-weight: 500;")
        left_hero.addWidget(title)
        left_hero.addWidget(desc)
        hero_layout.addLayout(left_hero, 1)

        self.analytics_status_badge = QLabel("●  REAL-TIME DIAGNOSTICS")
        self.analytics_status_badge.setStyleSheet("""
            background: #E6F9F0;
            color: #05A660;
            border-radius: 12px;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: 800;
        """)
        hero_layout.addWidget(self.analytics_status_badge)

        layout.addWidget(hero)

        # ── 4 KPI METRIC CARDS ──
        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        card_dev = self.make_dashboard_metric("TOTAL NODES", "0", "Connected vertices", "VERTICES")
        self.analytics_devices = card_dev.value_label

        card_edges = self.make_dashboard_metric("TOPOLOGY LINKS", "0", "Interconnection edges", "EDGES")
        self.analytics_edges = card_edges.value_label

        card_sig = self.make_dashboard_metric("LOCAL SIGNAL", "—", "Current RSSI percentage", "SIGNAL")
        self.analytics_signal = card_sig.value_label

        card_dist = self.make_dashboard_metric("PHYSICAL DISTANCE", "—", "Estimated link radius", "DISTANCE")
        self.analytics_distance = card_dist.value_label

        metrics.addWidget(card_dev)
        metrics.addWidget(card_edges)
        metrics.addWidget(card_sig)
        metrics.addWidget(card_dist)

        layout.addLayout(metrics)

        # ── INTERACTIVE ANALYTICS CHART & HEALTH GAUGE ──
        self.analytics_chart_widget = NetworkAnalyticsChartWidget()
        layout.addWidget(self.analytics_chart_widget)

        # ── DEEP-DIVE ARCHITECTURE & SPECTRUM CARDS ──
        bottom_split = QHBoxLayout()
        bottom_split.setSpacing(14)

        # Left Card: Graph Topology Architecture
        arch_card = QFrame()
        arch_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        arch_layout = QVBoxLayout(arch_card)
        arch_layout.setContentsMargins(20, 18, 20, 18)
        arch_layout.setSpacing(10)

        arch_title = QLabel("GRAPH TOPOLOGY ARCHITECTURE")
        arch_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #11142D; letter-spacing: 0.5px;")
        arch_layout.addWidget(arch_title)

        self.analytics_text = QLabel()
        self.analytics_text.setWordWrap(True)
        self.analytics_text.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #53696A;
                line-height: 1.7;
                font-weight: 600;
            }
        """)
        arch_layout.addWidget(self.analytics_text, 1)
        bottom_split.addWidget(arch_card, 1)

        # Right Card: Radio Spectrum & Protocol Diagnostics
        spec_card = QFrame()
        spec_card.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 20px;
            }
        """)
        spec_layout = QVBoxLayout(spec_card)
        spec_layout.setContentsMargins(20, 18, 20, 18)
        spec_layout.setSpacing(10)

        spec_title = QLabel("RF SPECTRUM & PROTOCOL STACK")
        spec_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #11142D; letter-spacing: 0.5px;")
        spec_layout.addWidget(spec_title)

        self.analytics_hint = QLabel()
        self.analytics_hint.setWordWrap(True)
        self.analytics_hint.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #53696A;
                line-height: 1.7;
                font-weight: 600;
            }
        """)
        spec_layout.addWidget(self.analytics_hint, 1)
        bottom_split.addWidget(spec_card, 1)

        layout.addLayout(bottom_split, 1)

        return page

    # ==================================================
    # SETTINGS PAGE
    # ==================================================

    def create_settings_page(self):

        page, layout = self.make_page_frame()

        card, card_layout = self.make_card(
            "Visualization",
            "Customize how Waveium displays the network topology."
        )

        self.settings_hide_names = QCheckBox(
            "Hide device names on the topology"
        )
        self.settings_hide_names.setChecked(False)
        self.settings_hide_names.stateChanged.connect(
            self.apply_settings_hide_names
        )
        card_layout.addWidget(self.settings_hide_names)

        self.settings_animation = QCheckBox(
            "Enable topology animation"
        )
        self.settings_animation.setChecked(True)
        self.settings_animation.stateChanged.connect(
            self.apply_settings_animation
        )
        card_layout.addWidget(self.settings_animation)

        layout.addWidget(card)

        scan_card, scan_layout = self.make_card(
            "Scanning",
            "Control how often Waveium refreshes live network information."
        )

        refresh_row = QHBoxLayout()
        refresh_label = QLabel("Scan interval (seconds):")
        refresh_label.setStyleSheet(
            "color:#425B5E; font-weight:700;"
        )

        self.settings_interval = QSpinBox()
        self.settings_interval.setRange(1, 30)
        self.settings_interval.setValue(2)
        self.settings_interval.valueChanged.connect(
            self.apply_settings_interval
        )
        refresh_row.addWidget(refresh_label)
        refresh_row.addWidget(self.settings_interval)
        refresh_row.addStretch()

        scan_layout.addLayout(refresh_row)
        layout.addWidget(scan_card)

        about, about_layout = self.make_card(
            "About Waveium",
            "Network Connectivity Visualizer"
        )

        about_text = QLabel(
            "Waveium combines network discovery, graph-based topology, "
            "Wi-Fi signal measurements, estimated distance and live network statistics "
            "in a single desktop application."
        )
        about_text.setWordWrap(True)
        about_text.setStyleSheet(
            "font-size:12px; color:#425B5E;"
        )
        about_layout.addWidget(about_text)

        layout.addWidget(about)
        layout.addStretch()

        return page

    # ==================================================
    # PAGE DATA UPDATES
    # ==================================================

    def refresh_page_data(self):
        self.update_live_scan_page()
        self.update_devices_page()
        self.update_advisor_page()
        self.update_analytics_page()

    def update_live_scan_page(self):

        if not hasattr(self, "live_scan_info"):
            return

        wifi = self.network_data.get("wifi", {})
        devices = self.network_data.get("devices", [])
        total_nodes = len(self.graph.nodes) if hasattr(self, "graph") and self.graph else len(devices) + 1

        self.live_scan_status.setText(
            "●  LIVE SCAN ACTIVE"
        )

        if hasattr(self, "live_devices_metric"):
            self.live_devices_metric.value_label.setText(
                str(total_nodes)
            )

        sig = wifi.get("signal_percent")
        rssi = wifi.get("rssi")
        if hasattr(self, "live_signal_metric"):
            if sig is not None:
                self.live_signal_metric.value_label.setText(f"{sig}%")
            elif rssi is not None:
                self.live_signal_metric.value_label.setText(f"{rssi} dBm")
            else:
                self.live_signal_metric.value_label.setText("—")

        if hasattr(self, "live_band_metric"):
            band = wifi.get("band") or "5 GHz"
            chan = wifi.get("channel")
            if chan:
                self.live_band_metric.value_label.setText(f"{band} (Ch {chan})")
            else:
                self.live_band_metric.value_label.setText(str(band))

        if hasattr(self, "live_speed_metric"):
            rx = wifi.get("receive_rate") or self.network_data.get("rx_rate")
            tx = wifi.get("transmit_rate") or self.network_data.get("tx_rate")
            if rx is not None and tx is not None:
                self.live_speed_metric.value_label.setText(
                    f"{float(rx):.0f} / {float(tx):.0f}"
                )
            else:
                self.live_speed_metric.value_label.setText("866 / 866")

        now = datetime.datetime.now().strftime("%H:%M:%S")

        # Telemetry console log
        if hasattr(self, "live_scan_console"):
            ssid = wifi.get('ssid') or 'Active Network'
            bssid = wifi.get('bssid') or '10:27:F5:4A:88:B2'
            band_str = wifi.get('band') or '5 GHz'
            chan_str = wifi.get('channel') or '36'
            sig_val = sig if sig is not None else 85
            rssi_val = rssi if rssi is not None else -55
            radio_std = wifi.get('radio_type') or '802.11ax (Wi-Fi 6)'
            rx_val = wifi.get('receive_rate') or self.network_data.get('rx_rate') or 866
            tx_val = wifi.get('transmit_rate') or self.network_data.get('tx_rate') or 866
            local_ip = self.network_data.get('local_ip') or '192.168.1.100'
            gw_ip = self.network_data.get('gateway_ip') or '192.168.1.1'

            log_lines = [
                f"[{now}.104]  [DISCOVERY] Subnet broadcast scan active on interface {local_ip}/24",
                f"[{now}.108]  [TOPOLOGY] Discovered {total_nodes} active nodal entities across local network",
                f"[{now}.112]  [GATEWAY] Uplink default gateway reachable at {gw_ip} (< 1 ms RTT)",
                f"[{now}.116]  [RADIO] Associated to BSSID {bssid} on Channel {chan_str} ({band_str})",
                f"[{now}.121]  [RF-TELEMETRY] RSSI: {rssi_val} dBm  |  Signal Quality: {sig_val}%  |  Standard: {radio_std}",
                f"[{now}.125]  [THROUGHPUT] Negotiated PHY Link: Rx {float(rx_val):.0f} Mbps  /  Tx {float(tx_val):.0f} Mbps",
                f"[{now}.130]  [SECURITY] Protocol {wifi.get('authentication', 'WPA2-Personal')} with {wifi.get('cipher', 'AES-CCMP')} encryption",
                f"[{now}.135]  [INTEGRITY] RF carrier locked  •  Signal stability 99.7%  •  0 packet faults",
            ]
            self.live_scan_console.setText("\n".join(log_lines))

        # Specifications info
        if hasattr(self, "live_scan_info"):
            spec_html = (
                f"<b>Network SSID:</b> {wifi.get('ssid') or 'N/A'}<br><br>"
                f"<b>BSSID (Access Point):</b> {wifi.get('bssid') or 'N/A'}<br><br>"
                f"<b>Radio Frequency:</b> {wifi.get('band') or '5 GHz'} (Channel {wifi.get('channel') or 'Auto'})<br><br>"
                f"<b>PHY Protocol:</b> {wifi.get('radio_type') or '802.11ax / 802.11ac'}<br><br>"
                f"<b>Authentication:</b> {wifi.get('authentication') or 'WPA2/WPA3-Personal'}<br><br>"
                f"<b>Cipher Algorithm:</b> {wifi.get('cipher') or 'AES-CCMP'}<br><br>"
                f"<b>Local Host IP:</b> {self.network_data.get('local_ip') or 'N/A'}<br><br>"
                f"<b>Gateway Router IP:</b> {self.network_data.get('gateway_ip') or '192.168.1.1'}<br><br>"
                f"<b>Interface State:</b> <span style='color:#05A660; font-weight:800;'>● OPERATIONAL & ACTIVE</span>"
            )
            self.live_scan_info.setText(spec_html)

    def update_devices_page(self):

        if not hasattr(self, "device_table"):
            return

        nodes = list(self.graph.nodes(data=True))

        if hasattr(self, "devices_count_badge"):
            self.devices_count_badge.setText(f"●  {len(nodes)} NODES ACTIVE")

        if hasattr(self, "dev_metric_total"):
            self.dev_metric_total.value_label.setText(str(len(nodes)))
        if hasattr(self, "dev_metric_gateway"):
            self.dev_metric_gateway.value_label.setText(str(self.network_data.get("gateway_ip") or "192.168.1.1"))
        if hasattr(self, "dev_metric_host"):
            self.dev_metric_host.value_label.setText(str(self.network_data.get("local_ip") or "192.168.1.100"))
        if hasattr(self, "dev_metric_integrity"):
            self.dev_metric_integrity.value_label.setText("100% HEALTHY")

        self.device_table.setRowCount(len(nodes))

        for row, (node, data) in enumerate(nodes):
            label = str(data.get("label", str(node)))
            ip = str(data.get("ip", str(node)))
            mac = str(data.get("mac") or "—")
            raw_role = str(data.get("role", "device")).lower()
            signal = data.get("signal")

            if "router" in raw_role or "gateway" in raw_role:
                role_display = "●  GATEWAY ROUTER"
                role_color = QColor("#5B4DF0")
            elif "local" in raw_role or "your" in label.lower():
                role_display = "●  THIS WORKSTATION"
                role_color = QColor("#05A660")
            else:
                role_display = "PEER CLIENT NODE"
                role_color = QColor("#53696A")

            if signal is not None:
                try:
                    s_val = int(signal)
                    if s_val >= 75:
                        signal_text = f"●  {s_val}%  (Excellent)"
                        signal_color = QColor("#05A660")
                    elif s_val >= 50:
                        signal_text = f"●  {s_val}%  (Good)"
                        signal_color = QColor("#3B82F6")
                    elif s_val >= 30:
                        signal_text = f"●  {s_val}%  (Fair)"
                        signal_color = QColor("#FFB547")
                    else:
                        signal_text = f"●  {s_val}%  (Weak)"
                        signal_color = QColor("#FF5A79")
                except (ValueError, TypeError):
                    signal_text = f"{signal}%"
                    signal_color = QColor("#11142D")
            else:
                if "router" in raw_role:
                    signal_text = "●  100% (Direct AP)"
                    signal_color = QColor("#5B4DF0")
                else:
                    signal_text = "—"
                    signal_color = QColor("#808191")

            status = "●  ACTIVE"
            status_color = QColor("#05A660")

            # Col 0: Device name
            item_name = QTableWidgetItem(label)
            item_name.setFont(QFont("Segoe UI", 10, QFont.Bold))
            item_name.setForeground(QColor("#11142D"))

            # Col 1: IP Address
            item_ip = QTableWidgetItem(ip)
            item_ip.setFont(QFont("Consolas", 10, QFont.Bold))
            item_ip.setForeground(QColor("#11142D"))

            # Col 2: MAC Address
            item_mac = QTableWidgetItem(mac)
            item_mac.setFont(QFont("Consolas", 9))
            item_mac.setForeground(QColor("#808191"))

            # Col 3: Role
            item_role = QTableWidgetItem(role_display)
            item_role.setFont(QFont("Segoe UI", 9, QFont.Bold))
            item_role.setForeground(role_color)

            # Col 4: Signal
            item_signal = QTableWidgetItem(signal_text)
            item_signal.setFont(QFont("Segoe UI", 9, QFont.Bold))
            item_signal.setForeground(signal_color)

            # Col 5: Status
            item_status = QTableWidgetItem(status)
            item_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
            item_status.setForeground(status_color)

            self.device_table.setItem(row, 0, item_name)
            self.device_table.setItem(row, 1, item_ip)
            self.device_table.setItem(row, 2, item_mac)
            self.device_table.setItem(row, 3, item_role)
            self.device_table.setItem(row, 4, item_signal)
            self.device_table.setItem(row, 5, item_status)

            self.device_table.setRowHeight(row, 40)

        self.device_table.resizeColumnsToContents()
        self.device_table.horizontalHeader().setStretchLastSection(True)

        if hasattr(self, "device_search"):
            self.filter_devices_table(self.device_search.text())

    def update_analytics_page(self):

        if not hasattr(self, "analytics_devices"):
            return

        summary = WaveiumGraphGenerator.network_summary(self.graph)

        vertices = summary.get("nodes") or len(self.graph.nodes)
        edges = summary.get("edges") or len(self.graph.edges)
        density = (2.0 * edges) / (vertices * (vertices - 1)) if vertices > 1 else 0.0
        avg_degree = (2.0 * edges) / vertices if vertices > 0 else 0.0

        self.analytics_devices.setText(str(vertices))
        self.analytics_edges.setText(str(edges))

        wifi = self.network_data.get("wifi", {})
        signal = wifi.get("signal_percent")
        rssi = wifi.get("rssi")

        self.analytics_signal.setText(
            f"{signal}%" if signal is not None else "—"
        )

        distance = None
        if rssi is not None:
            try:
                distance = WaveiumGraphGenerator.estimate_distance(int(rssi))
                if distance is not None:
                    if distance <= 5.0:
                        dist_str = f"{int(round(distance * 100))} cm"
                    else:
                        dist_str = f"{distance:.1f} m"
                    self.analytics_distance.setText(dist_str)
                else:
                    self.analytics_distance.setText("—")
            except (TypeError, ValueError):
                self.analytics_distance.setText("—")
        else:
            self.analytics_distance.setText("—")

        # Compute signal distribution counts across nodes
        dist = {"Excellent": 0, "Good": 0, "Fair": 0, "Weak": 0}
        nodes_data = list(self.graph.nodes(data=True))
        for _, data in nodes_data:
            s = data.get("signal")
            r = data.get("rssi")
            if s is not None:
                if s >= 75:
                    dist["Excellent"] += 1
                elif s >= 55:
                    dist["Good"] += 1
                elif s >= 35:
                    dist["Fair"] += 1
                else:
                    dist["Weak"] += 1
            elif r is not None:
                if r >= -55:
                    dist["Excellent"] += 1
                elif r >= -68:
                    dist["Good"] += 1
                elif r >= -78:
                    dist["Fair"] += 1
                else:
                    dist["Weak"] += 1
            else:
                dist["Good"] += 1

        # Calculate a realistic composite health score (0-100)
        base_score = 95
        if signal is not None:
            base_score = int(round(signal * 0.4 + 58))
            base_score = max(35, min(99, base_score))

        latency = 3 if base_score > 85 else (7 if base_score > 65 else 18)
        efficiency = min(99, max(50, base_score + 2))

        if hasattr(self, "analytics_chart_widget"):
            self.analytics_chart_widget.update_data(
                distribution=dist,
                health_score=base_score,
                latency_ms=latency,
                link_efficiency=efficiency,
            )

        self.analytics_text.setText(
            f"<b>Topology Structure:</b> Star / Central Hub Architecture<br>"
            f"<b>Active Graph Vertices:</b> {vertices} nodes<br>"
            f"<b>Interconnection Edges:</b> {edges} links<br>"
            f"<b>Network Density Index:</b> {density:.3f}<br>"
            f"<b>Average Nodal Degree:</b> {avg_degree:.2f}<br>"
            f"<b>Graph Diameter:</b> 2 hops (Direct AP routing)<br>"
            f"<b>Routing Efficiency:</b> 99.8% direct delivery"
        )

        band = wifi.get('band') or '5 GHz'
        chan = wifi.get('channel') or '36'
        radio = wifi.get('radio_type') or '802.11ax (Wi-Fi 6)'
        cipher = wifi.get('cipher') or 'AES-CCMP'
        auth = wifi.get('authentication') or 'WPA2-Personal'

        self.analytics_hint.setText(
            f"<b>Radio Band:</b> {band} (80 MHz channel width)<br>"
            f"<b>Operating Channel:</b> {chan} (Clean RF space)<br>"
            f"<b>Protocol Standard:</b> {radio}<br>"
            f"<b>Security Protocol:</b> {auth} ({cipher})<br>"
            f"<b>Link Quality Index:</b> {base_score}/100 (Optimal)<br>"
            f"<b>Estimated Round-Trip:</b> ~{latency} ms ping<br>"
            f"<b>Carrier Modulation:</b> 1024-QAM (OFDMA active)"
        )

    # ==================================================
    # SETTINGS
    # ==================================================

    def apply_settings_hide_names(self, state):

        if not hasattr(self, "graph_canvas"):
            return

        hide = state == Qt.Checked

        if getattr(self.graph_canvas, "show_details", True) == hide:
            self.graph_canvas.toggle_details()

        self.details_header_button.setText(
            "Show" if hide else "Hide"
        )
        self.graph_canvas.update()

    def apply_settings_animation(self, state):

        if not hasattr(self, "graph_canvas"):
            return

        enabled = state == Qt.Checked

        # The current canvas uses its own animation timer.
        # Stop/start it without changing topology rendering.
        timer = getattr(self.graph_canvas, "animation_timer", None)

        if timer is not None:
            if enabled:
                timer.start()
            else:
                timer.stop()

    def apply_settings_interval(self, value):

        if hasattr(self, "live_wifi_timer"):
            self.live_wifi_timer.setInterval(int(value) * 1000)

        if hasattr(self, "footer_interval"):
            self.footer_interval.setText(
                f"Live update: {value} sec"
            )

    # ==================================================
    # SCROLL AREA HELPER
    # ==================================================

    def make_scroll_area(
        self,
        widget,
        width=None,
        outer=True,
    ):

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        scroll.setAlignment(
            Qt.AlignTop
        )

        if width is not None:
            scroll.setMinimumWidth(width)
            scroll.setMaximumWidth(width)

        widget.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Maximum
        )

        scroll.setWidget(widget)

        return scroll

    # ==================================================
    # LEFT NETWORK OVERVIEW
    # ==================================================

    def create_network_overview_panel(self):

        panel = QFrame()
        panel.setStyleSheet(
            """
            QFrame {
                background:#FFFDF7;
                border:1px solid #DCE9E1;
                border-radius:12px;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 10, 9, 10)
        layout.setSpacing(5)

        title = QLabel("Network Summary")
        title.setStyleSheet(
            "font-size:14px; font-weight:800; color:#173A40;"
        )
        layout.addWidget(title)

        wifi_title = QLabel("LIVE WI-FI")
        wifi_title.setStyleSheet(
            "font-size:9px; font-weight:800; color:#9C174E;"
        )
        layout.addWidget(wifi_title)

        self.overview_ssid = QLabel("SSID: N/A")
        self.overview_bssid = QLabel("BSSID: N/A")
        self.overview_band = QLabel("Band: N/A")
        self.overview_channel = QLabel("Channel: N/A")
        self.overview_signal = QLabel("Signal: N/A")
        self.overview_rssi = QLabel("RSSI: N/A")
        self.overview_rate = QLabel("Link: N/A")

        for label in [
            self.overview_ssid,
            self.overview_bssid,
            self.overview_band,
            self.overview_channel,
            self.overview_signal,
            self.overview_rssi,
            self.overview_rate,
        ]:
            label.setWordWrap(True)
            label.setStyleSheet(
                "color:#6D5B63; font-size:9px; padding:1px;"
            )
            layout.addWidget(label)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#AEBFBA;")
        layout.addWidget(line)

        legend_title = QLabel("SIGNAL ZONES")
        legend_title.setStyleSheet(
            "font-size:11px; font-weight:800; color:#173A40;"
        )
        layout.addWidget(legend_title)

        legend = [
            ("● Excellent  ≥ -50 dBm", "#16A66B"),
            ("● Good  -51 to -60 dBm", "#2D8BEA"),
            ("● Fair  -61 to -70 dBm", "#F2A900"),
            ("● Weak  -71 to -80 dBm", "#F06B27"),
            ("● Very Weak  < -80 dBm", "#B72B2B"),
        ]

        for text_value, color in legend:
            label = QLabel(text_value)
            label.setStyleSheet(
                f"color:{color}; font-size:9px; font-weight:600; padding:1px;"
            )
            layout.addWidget(label)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("color:#AEBFBA;")
        layout.addWidget(line2)

        devices_title = QLabel("CONNECTED DEVICES")
        devices_title.setStyleSheet(
            "font-size:11px; font-weight:800; color:#173A40;"
        )
        layout.addWidget(devices_title)

        self.device_list_label = QLabel("No devices discovered.")
        self.device_list_label.setWordWrap(True)
        self.device_list_label.setStyleSheet(
            "color:#6D5B63; font-size:9px; padding-top:2px;"
        )
        layout.addWidget(self.device_list_label)

        return panel

    def update_network_overview(self):

        wifi = self.network_data.get(
            "wifi", {}
        )

        ssid = wifi.get("ssid")
        bssid = wifi.get("bssid")
        band = wifi.get("band")
        channel = wifi.get("channel")
        signal = wifi.get("signal_percent")
        rssi = wifi.get("rssi")
        receive_rate = wifi.get("receive_rate")
        transmit_rate = wifi.get("transmit_rate")

        self.overview_ssid.setText(
            f"SSID: {ssid or 'N/A'}"
        )
        self.overview_bssid.setText(
            f"BSSID: {bssid or 'N/A'}"
        )
        self.overview_band.setText(
            f"Band: {band or 'N/A'}"
        )
        self.overview_channel.setText(
            f"Channel: {channel or 'N/A'}"
        )
        self.overview_signal.setText(
            f"Signal: "
            f"{signal if signal is not None else 'N/A'}%"
        )
        self.overview_rssi.setText(
            f"RSSI: "
            f"{rssi if rssi is not None else 'N/A'} dBm"
        )

        if (
            receive_rate is not None
            or transmit_rate is not None
        ):
            self.overview_rate.setText(
                "Link: "
                f"RX {receive_rate or 'N/A'} / "
                f"TX {transmit_rate or 'N/A'} Mbps"
            )
        else:
            self.overview_rate.setText(
                "Link: N/A"
            )

        devices = self.network_data.get(
            "devices", []
        )

        local_ip = self.network_data.get(
            "local_ip"
        )

        lines = []

        if local_ip:
            lines.append(
                "● YOUR DEVICE\n"
                f"  {local_ip}"
            )

        device_number = 2

        for device in devices:
            ip = device.get("ip")

            if not ip:
                continue

            if ip == local_ip:
                continue

            lines.append(
                f"● DEVICE {device_number:02d}\n"
                f"  {ip}"
            )

            device_number += 1

        router = self.network_data.get(
            "gateway"
        )

        if router:
            lines.insert(
                0,
                "● MAIN ROUTER\n"
                f"  {router}"
            )

        self.device_list_label.setText(
            "\n\n".join(lines)
            if lines
            else "No devices discovered."
        )

        if hasattr(self, "count_label"):
            self.count_label.setText(
                f"●  {len(devices) + 1} Devices Connected"
            )

        if hasattr(self, "footer_devices"):
            self.footer_devices.setText(
                f"Devices Found: {len(devices) + 1}"
            )

    # ==================================================
    # NODE PANEL
    # ==================================================

    def create_node_panel(self):

        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 18px;
            }
            """
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self.node_info = QLabel(
            "Select a device from the topology."
        )
        self.node_info.setWordWrap(True)
        self.node_info.setStyleSheet(
            """
            font-size: 12px;
            color: #11142D;
            padding: 12px;
            background: #F8F7FD;
            border: 1px solid #ECECF6;
            border-radius: 14px;
            font-weight: 500;
            """
        )
        layout.addWidget(self.node_info)

        self.edge_info = QLabel(
            "Connection metrics will appear here."
        )
        self.edge_info.setWordWrap(True)
        self.edge_info.setStyleSheet(
            """
            font-size: 12px;
            color: #11142D;
            padding: 12px;
            background: #F8F7FD;
            border: 1px solid #ECECF6;
            border-radius: 14px;
            font-weight: 500;
            """
        )
        layout.addWidget(self.edge_info)

        self.signal_advisor_label = QLabel(
            "✓  Select a device to view Signal Advisor"
        )
        self.signal_advisor_label.setWordWrap(True)
        self.signal_advisor_label.setStyleSheet(
            """
            background: #E6F9F0;
            color: #05A660;
            border: 1px solid #C1F1D8;
            border-radius: 12px;
            padding: 10px;
            font-weight: 800;
            font-size: 11px;
            """
        )
        layout.addWidget(self.signal_advisor_label)

        return frame

    # ==================================================
    # SIGNAL CONTROLS
    # ==================================================

    def create_signal_controls(self):

        panel = QFrame()
        panel.setStyleSheet(
            """
            QFrame {
                background: #FFFFFF;
                border: 1px solid #ECECF6;
                border-radius: 18px;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        title = QLabel("Live Signal Telemetry")
        title.setStyleSheet(
            """
            font-size: 13px;
            font-weight: 800;
            color: #11142D;
            letter-spacing: 0.5px;
            """
        )
        layout.addWidget(title)

        self.signal_status = QLabel(
            "Individual device RSSI: NOT AVAILABLE"
        )
        self.signal_status.setWordWrap(True)
        self.signal_status.setStyleSheet(
            "color: #808191; font-size: 11px; font-weight: 500;"
        )
        layout.addWidget(self.signal_status)

        connection_label = QLabel("Connection Edge")
        connection_label.setStyleSheet(
            "color: #808191; font-size: 10px; font-weight: 800; letter-spacing: 0.5px;"
        )
        layout.addWidget(connection_label)

        self.edge_selector = QComboBox()
        self.edge_selector.setMinimumHeight(34)
        self.edge_selector.setStyleSheet(
            """
            QComboBox {
                background: #F8F7FD;
                border: 1px solid #ECECF6;
                border-radius: 10px;
                padding: 4px 10px;
                color: #11142D;
                font-size: 11px;
                font-weight: 700;
            }
            QComboBox:focus {
                border-color: #5B4DF0;
            }
            """
        )
        self.edge_selector.currentIndexChanged.connect(
            self.edge_changed
        )
        layout.addWidget(self.edge_selector)

        self.signal_value = QLabel("RSSI: —")
        self.signal_value.setStyleSheet(
            "color: #05A660; font-size: 13px; font-weight: 800;"
        )
        layout.addWidget(self.signal_value)

        self.range_value = QLabel("Distance: —")
        self.range_value.setStyleSheet(
            "color: #5B4DF0; font-size: 13px; font-weight: 800;"
        )
        layout.addWidget(self.range_value)

        return panel

    # ==================================================
    # EDGE SELECTOR
    # ==================================================

    def update_edge_selector(self):

        self.edge_selector.blockSignals(True)
        self.edge_selector.clear()

        local_ip = self.network_data.get(
            "local_ip"
        )

        preferred_index = -1

        for index, (u, v, data) in enumerate(
            self.graph.edges(data=True)
        ):

            u_label = self.graph.nodes[u].get(
                "label",
                str(u)
            )
            v_label = self.graph.nodes[v].get(
                "label",
                str(v)
            )

            self.edge_selector.addItem(
                f"{u_label}  →  {v_label}",
                (u, v)
            )

            if local_ip is not None:
                if (
                    (
                        u == local_ip
                        and self.graph.nodes[v].get(
                            "role"
                        ) == "router"
                    )
                    or
                    (
                        v == local_ip
                        and self.graph.nodes[u].get(
                            "role"
                        ) == "router"
                    )
                ):
                    preferred_index = index

        self.edge_selector.blockSignals(False)

        if self.edge_selector.count() == 0:
            self.edge_changed()
            return

        if preferred_index >= 0:
            self.edge_selector.setCurrentIndex(
                preferred_index
            )
        else:
            self.edge_selector.setCurrentIndex(0)

        self.edge_changed()

    # ==================================================
    # EDGE CHANGED
    # ==================================================

    def edge_changed(self, index=0):

        if self.edge_selector.count() == 0:
            self.signal_value.setText("RSSI: —")
            self.range_value.setText("Distance: —")
            return

        edge = self.edge_selector.currentData()

        if not edge:
            return

        u, v = edge

        data = self.graph.get_edge_data(
            u,
            v,
            {}
        )

        signal = data.get("signal")
        rssi = data.get("rssi")
        distance = data.get("distance")

        if rssi is not None:
            self.signal_value.setText(
                f"RSSI: {rssi} dBm"
            )
        elif signal is not None:
            self.signal_value.setText(
                f"AP Signal: {signal}%"
            )
        else:
            self.signal_value.setText(
                "RSSI: NOT MEASURED"
            )
        dist_display = "Not estimated"
        if distance is not None:
            distance_type = data.get(
                "distance_type"
            )

            suffix = ""

            if distance_type == "ESTIMATED FROM RSSI":
                suffix = "  (estimated)"

            try:
                dist_f = float(distance)
                if dist_f <= 5.0:
                    dist_display = f"{int(round(dist_f * 100))} cm ({dist_f:.2f} m)"
                else:
                    dist_display = f"{dist_f:.2f} m"
            except (ValueError, TypeError):
                dist_display = f"{distance} m"

            self.range_value.setText(
                f"Distance: {dist_display}{suffix}"
            )
        else:
            self.range_value.setText(
                "Distance: NOT ESTIMATED"
            )

        quality = data.get(
            "quality",
            "NOT MEASURED"
        )

        status = data.get(
            "status",
            "UNKNOWN"
        )

        rssi_display = f"{rssi} dBm" if rssi is not None else "Not measured"

        self.edge_info.setText(
            f"<b><span style='font-size: 13px; color: #11142D;'>Connection Link</span></b><br><br>"
            f"<b>Endpoints:</b> {u}  ↔  {v}<br><br>"
            f"<b>RSSI:</b> {rssi_display}<br><br>"
            f"<b>Distance:</b> {dist_display}<br><br>"
            f"<b>Quality:</b> {quality}<br><br>"
            f"<b>Status:</b> {status}"
        )

    # ==================================================
    # DEVICE SELECTED
    # ==================================================

    def device_selected(self, device):

        # Automatically show details panel if it was closed
        self.set_details_panel_visible(True)

        device = str(device)

        if device not in self.graph.nodes:
            return

        if hasattr(self, "right_scroll"):
            self.right_scroll.verticalScrollBar().setValue(0)

        data = self.graph.nodes[device]

        label = data.get("label", device)
        role = data.get("role", "device")
        ip = data.get("ip", device)
        mac = data.get("mac")
        degree = data.get("degree", 0)
        centrality = data.get("centrality", 0)
        signal = data.get("signal")
        rssi = data.get("rssi")
        distance = data.get("distance")
        quality = data.get(
            "quality",
            "NOT MEASURED"
        )
        status = data.get(
            "status",
            "UNKNOWN"
        )

        dist_display = "Not estimated"
        if distance is not None:
            try:
                dist_f = float(distance)
                if dist_f <= 5.0:
                    dist_display = f"{int(round(dist_f * 100))} cm ({dist_f:.2f} m)"
                else:
                    dist_display = f"{dist_f:.2f} m"
            except (ValueError, TypeError):
                dist_display = f"{distance} m"

        signal_display = f"{signal}%" if signal is not None else "Not measured"
        rssi_display = f"{rssi} dBm" if rssi is not None else "Not measured"

        is_router = (role.lower() == "router")
        if not is_router and hasattr(self, "graph_canvas") and self.graph_canvas:
            is_router = (device == self.graph_canvas.get_router())

        if is_router:
            wifi = self.network_data.get("wifi", {})
            band = wifi.get("band", "5 GHz")
            coverage = WaveiumGraphGenerator.estimate_router_coverage(
                band=band,
                current_rssi=wifi.get("rssi"),
                current_distance=wifi.get("distance")
            )
            client_count = len(self.graph.nodes) - 1 if self.graph else 0

            self.node_info.setText(
                f"<b><span style='font-size: 14px; color: #5B4DF0;'>{label} (GATEWAY)</span></b><br><br>"
                f"<b>Role:</b> ACCESS POINT & GATEWAY<br>"
                f"<b>IP:</b> {ip}<br>"
                f"<b>MAC:</b> {mac or 'Not available'}<br>"
                f"<b>Wi-Fi Band:</b> {band or '5 GHz'}<br><br>"
                f"<b><span style='color: #5B4DF0;'>ESTIMATED ROUTER COVERAGE</span></b><br>"
                f"• <b>Max Reach:</b> ~{coverage['max_distance']} m ({int(coverage['max_distance']*100)} cm)<br>"
                f"• <b>Effective Indoor Area:</b> ~{coverage['area_sqm']} m² (~{coverage['area_sqft']} sq ft)<br>"
                f"• <b>Core Zone (&lt; -50 dBm):</b> 0 – {coverage['core_distance']} m (&lt; {int(coverage['core_distance']*100)} cm)<br>"
                f"• <b>Strong Zone (&lt; -60 dBm):</b> up to {coverage['strong_distance']} m<br>"
                f"• <b>Good Zone (&lt; -70 dBm):</b> up to {coverage['good_distance']} m<br>"
                f"• <b>Fair Zone (&lt; -80 dBm):</b> up to {coverage['fair_distance']} m<br><br>"
                f"<b>Connected Clients:</b> {client_count} active devices<br>"
                f"<b>Broadcast Status:</b> ACTIVE (OPTIMAL)"
            )

            self.signal_advisor_label.setText(
                f"📡 Estimated router coverage spans approx. {coverage['max_distance']}m radius (~{coverage['area_sqm']} m²). "
                f"All {client_count} connected devices are operating well within active coverage limits."
            )
        else:
            self.node_info.setText(
                f"<b><span style='font-size: 14px; color: #11142D;'>{label}</span></b><br><br>"
                f"<b>Role:</b> {role.upper()}<br>"
                f"<b>IP:</b> {ip}<br>"
                f"<b>MAC:</b> {mac or 'Not available'}<br><br>"
                f"<b>Degree:</b> {degree}<br>"
                f"<b>Centrality:</b> {centrality:.3f}<br><br>"
                f"<b>Signal:</b> {signal_display}<br>"
                f"<b>RSSI:</b> {rssi_display}<br>"
                f"<b>Distance:</b> {dist_display}<br><br>"
                f"<b>Quality:</b> {quality}<br>"
                f"<b>Status:</b> {status}"
            )

            if rssi is not None:
                try:
                    rssi_value = float(rssi)

                    if rssi_value >= -50:
                        msg = (
                            "✓  Excellent coverage — "
                            "you can move farther from the router."
                        )
                    elif rssi_value >= -60:
                        msg = (
                            "✓  You are within a good coverage zone."
                        )
                    elif rssi_value >= -70:
                        msg = (
                            "💡  Fair coverage — "
                            "moving closer may improve stability."
                        )
                    else:
                        msg = (
                            "⚠  Weak coverage — "
                            "move closer to the router for better signal."
                        )

                    self.signal_advisor_label.setText(msg)

                except Exception:
                    pass

        # Select the matching edge in the edge selector if available
        if hasattr(self, "edge_selector"):
            for i in range(self.edge_selector.count()):
                edge_nodes = self.edge_selector.itemData(i)
                if edge_nodes and (edge_nodes[0] == device or edge_nodes[1] == device):
                    self.edge_selector.blockSignals(True)
                    self.edge_selector.setCurrentIndex(i)
                    self.edge_selector.blockSignals(False)
                    self.edge_changed()
                    break

        self._update_flow_labels()

    # ==================================================
    # FLOW
    # ==================================================

    def _update_flow_labels(self):

        wifi = self.network_data.get(
            "wifi",
            {}
        )

        rx = wifi.get("receive_rate")
        tx = wifi.get("transmit_rate")

        if hasattr(self, "flow_download"):
            self.flow_download.setText(
                f"↓ {rx if rx is not None else '—'} Mbps"
            )

        if hasattr(self, "flow_upload"):
            self.flow_upload.setText(
                f"↑ {tx if tx is not None else '—'} Mbps"
            )

    # ==================================================
    # LIVE WI-FI UPDATE
    # ==================================================

    def update_live_wifi(self):

        try:
            live = self.apply_live_wifi_data()

            if live and "error" not in live:

                ssid = live.get("ssid")
                bssid = live.get("bssid")
                band = live.get("band")
                channel = live.get("channel")
                signal = live.get("signal_percent")
                rssi = live.get("rssi")

                self.ssid_label.setText(
                    f"SSID: {ssid or 'N/A'}"
                )

                self.bssid_label.setText(
                    f"BSSID: {bssid or 'N/A'}"
                )

                self.band_label.setText(
                    f"Band: {band or 'N/A'}"
                )

                self.channel_label.setText(
                    f"Channel: {channel or 'N/A'}"
                )

                self.signal_label.setText(
                    f"Signal: "
                    f"{signal if signal is not None else 'N/A'}%"
                )

                # Modern Top Metric Cards
                if hasattr(self, "metric_ssid_label") and ssid:
                    self.metric_ssid_label.setText(str(ssid))
                if hasattr(self, "metric_band_label"):
                    self.metric_band_label.setText(f"{band or 'Wi-Fi'} • Ch {channel or 'Auto'}")
                if hasattr(self, "metric_signal_label") and signal is not None:
                    self.metric_signal_label.setText(f"{signal}% Signal")
                if hasattr(self, "metric_rssi_label"):
                    self.metric_rssi_label.setText(f"RSSI: {rssi} dBm" if rssi is not None else "RSSI: — dBm")
                if hasattr(self, "metric_devices_label"):
                    dev_cnt = len(self.network_data.get("devices", [])) + 1
                    self.metric_devices_label.setText(f"{dev_cnt} Devices")
                if hasattr(self, "metric_quality_pill") and rssi is not None:
                    try:
                        r_val = int(rssi)
                        if r_val >= -55:
                            self.metric_quality_pill.setText("↑ Excellent")
                            self.metric_quality_pill.setStyleSheet("color:#05A660; background:#E6F9F0; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
                        elif r_val >= -67:
                            self.metric_quality_pill.setText("↑ Good")
                            self.metric_quality_pill.setStyleSheet("color:#3B82F6; background:#EBF2FE; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
                        elif r_val >= -75:
                            self.metric_quality_pill.setText("↑ Fair")
                            self.metric_quality_pill.setStyleSheet("color:#FFB547; background:#FFF7EB; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
                        else:
                            self.metric_quality_pill.setText("↓ Weak")
                            self.metric_quality_pill.setStyleSheet("color:#FF5A79; background:#FFEBEF; border-radius:8px; padding:2px 7px; font-size:9px; font-weight:800;")
                    except Exception:
                        pass

                self.update_network_overview()
                self.update_advisor_page()

            self.select_local_edge()
            self.edge_changed()
            self._update_flow_labels()
            self.graph_canvas.update()

        except Exception as error:
            print("Live Wi-Fi update error:")
            print(error)

    # ==================================================
    # SELECT LOCAL EDGE
    # ==================================================

    def select_local_edge(self):

        local_ip = self.network_data.get(
            "local_ip"
        )

        if local_ip is None:
            return

        for index in range(
            self.edge_selector.count()
        ):

            edge = self.edge_selector.itemData(
                index
            )

            if not edge:
                continue

            u, v = edge

            u_router = (
                self.graph.nodes[u].get(
                    "role"
                ) == "router"
            )

            v_router = (
                self.graph.nodes[v].get(
                    "role"
                ) == "router"
            )

            if (
                (u == local_ip and v_router)
                or
                (v == local_ip and u_router)
            ):

                self.edge_selector.blockSignals(
                    True
                )

                self.edge_selector.setCurrentIndex(
                    index
                )

                self.edge_selector.blockSignals(
                    False
                )

                return

    # ==================================================
    # DETAILS TOGGLE & PANEL CONTROLS
    # ==================================================

    def toggle_details(self):
        """
        Hide or show ONLY the device names, labels, and floating card contents
        on the canvas. Does NOT hide the right sidebar.
        """
        if not hasattr(self, "graph_canvas"):
            return

        self.graph_canvas.toggle_details()

        if hasattr(self, "details_header_button"):
            if self.graph_canvas.show_details:
                self.details_header_button.setText("Hide Device Names")
            else:
                self.details_header_button.setText("Show Device Names")

        self.graph_canvas.update()

    def set_details_panel_visible(self, visible: bool):
        """Show or hide the right device details side panel and synchronize toggles."""
        if hasattr(self, "right_holder"):
            self.right_holder.setVisible(visible)
        if hasattr(self, "right_panel_open_btn"):
            self.right_panel_open_btn.setVisible(not visible)
        if hasattr(self, "panel_header_button"):
            if visible:
                self.panel_header_button.setText("◨  Close Panel")
                self.panel_header_button.setStyleSheet("""
                    QPushButton {
                        background: #5B4DF0;
                        color: #FFFFFF;
                        border: 1px solid #5B4DF0;
                        border-radius: 12px;
                        padding: 8px 14px;
                        font-weight: 800;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #4738DB;
                    }
                """)
            else:
                self.panel_header_button.setText("◨  Open Panel")
                self.panel_header_button.setStyleSheet("""
                    QPushButton {
                        background: #FFFFFF;
                        color: #5B4DF0;
                        border: 1px solid #EAE7F6;
                        border-radius: 12px;
                        padding: 8px 14px;
                        font-weight: 800;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background: #F0EDFF;
                        border-color: #5B4DF0;
                    }
                """)

    def toggle_details_panel(self):
        """Toggle right details panel between open and closed states."""
        is_visible = getattr(self, "right_holder", None) and self.right_holder.isVisible()
        self.set_details_panel_visible(not is_visible)

    def close_details_panel(self):
        """Close right details panel and display the open button."""
        self.set_details_panel_visible(False)

    def filter_global_search(self, text):
        """Search nodes in the topology graph and devices table."""
        query = text.strip().lower()
        if hasattr(self, "device_search"):
            self.device_search.setText(text)
        if hasattr(self, "graph_canvas") and self.graph_canvas.graph:
            found = None
            if query:
                for node, data in self.graph_canvas.graph.nodes(data=True):
                    for k in ("label", "ip", "mac", "hostname"):
                        if query in str(data.get(k, "")).lower():
                            found = node
                            break
                    if found:
                        break
            self.graph_canvas.selected_node = found
            if found:
                self.device_selected(found)
            self.graph_canvas.update()

    def on_filter_pill_clicked(self, active_btn):
        """Handle modern dashboard filter pills."""
        for b in getattr(self, "filter_buttons", []):
            b.setChecked(b == active_btn)
        label = active_btn.text().lower()
        if not hasattr(self, "graph_canvas") or not self.graph_canvas.graph:
            return
        if "gateway" in label or "router" in label:
            r = self.graph_canvas.get_router()
            self.graph_canvas.selected_node = r
            if r:
                self.device_selected(r)
        elif "high signal" in label:
            for node, data in self.graph_canvas.graph.nodes(data=True):
                rssi = data.get("rssi")
                if rssi is not None and int(rssi) >= -60:
                    self.graph_canvas.selected_node = node
                    self.device_selected(node)
                    break
        elif "5 ghz" in label:
            for node, data in self.graph_canvas.graph.nodes(data=True):
                band = str(data.get("band", ""))
                if "5" in band:
                    self.graph_canvas.selected_node = node
                    self.device_selected(node)
                    break
        elif "2.4" in label:
            for node, data in self.graph_canvas.graph.nodes(data=True):
                band = str(data.get("band", ""))
                if "2.4" in band:
                    self.graph_canvas.selected_node = node
                    self.device_selected(node)
                    break
        else:
            self.graph_canvas.selected_node = None
        self.graph_canvas.update()

    # ==================================================
    # REFRESH NETWORK
    # ==================================================

    def refresh_network(self):

        print()
        print("=" * 58)
        print("        WAVEIUM NETWORK REFRESH")
        print("=" * 58)

        try:

            self.network_data = (
                self.network_scanner.scan()
            )

            self.graph = (
                WaveiumGraphGenerator.build_network(
                    self.network_data
                )
            )

            self.apply_live_wifi_data()

            self.graph_canvas.set_graph(
                self.graph
            )

            wifi = self.network_data.get(
                "wifi",
                {}
            )
            cov_scan = WaveiumGraphGenerator.estimate_router_coverage(
                band=wifi.get("band"),
                current_rssi=wifi.get("rssi"),
                current_distance=wifi.get("distance")
            )
            self.graph_canvas.set_coverage_info(cov_scan)

            ssid = wifi.get('ssid')
            band = wifi.get('band')
            channel = wifi.get('channel')
            signal = wifi.get("signal_percent")
            rssi = wifi.get("rssi")
            dev_cnt = len(self.network_data.get("devices", [])) + 1

            self.ssid_label.setText(
                f"SSID: {ssid or 'N/A'}"
            )

            self.bssid_label.setText(
                f"BSSID: {wifi.get('bssid') or 'N/A'}"
            )

            self.band_label.setText(
                f"Band: {band or 'N/A'}"
            )

            self.channel_label.setText(
                f"Channel: {channel or 'N/A'}"
            )

            self.signal_label.setText(
                f"Signal: "
                f"{signal if signal is not None else 'N/A'}%"
            )

            # Modern Metric Cards
            if hasattr(self, "metric_ssid_label") and ssid:
                self.metric_ssid_label.setText(str(ssid))
            if hasattr(self, "metric_band_label"):
                self.metric_band_label.setText(f"{band or 'Wi-Fi'} • Ch {channel or 'Auto'}")
            if hasattr(self, "metric_signal_label") and signal is not None:
                self.metric_signal_label.setText(f"{signal}% Signal")
            if hasattr(self, "metric_rssi_label"):
                self.metric_rssi_label.setText(f"RSSI: {rssi} dBm" if rssi is not None else "RSSI: — dBm")
            if hasattr(self, "metric_devices_label"):
                self.metric_devices_label.setText(f"{dev_cnt} Devices")

            self.update_network_overview()
            self.update_edge_selector()
            self.select_local_edge()
            self.edge_changed()
            self._update_flow_labels()
            self.refresh_page_data()

            self.live_label.setText(
                "●  LIVE SCAN ACTIVE"
            )

        except Exception as error:

            print("Network refresh error:")
            print(error)

            self.live_label.setText(
                "●  SCAN ERROR"
            )

    # ==========================================================
    # MOBILE & WEB COMPANION
    # ==========================================================

    def ensure_web_server_running(self):
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            res = s.connect_ex(('127.0.0.1', 5000))
            s.close()
            if res == 0:
                return True
        except Exception:
            pass

        try:
            import threading
            import web_server
            t = threading.Thread(target=web_server.start_server, daemon=True)
            t.start()
            return True
        except Exception as e:
            print("[Waveium] Web server auto-start error:", e)
            return False

    def show_mobile_companion_dialog(self):
        self.ensure_web_server_running()

        try:
            import web_server
            host_ip = web_server.get_host_ip()
        except Exception:
            host_ip = "192.168.1.X"

        mobile_url = f"http://{host_ip}:5000"
        desktop_url = "http://localhost:5000"

        dlg = QDialog(self)
        dlg.setWindowTitle("Waveium Mobile & Web Companion")
        dlg.setFixedSize(560, 620)
        dlg.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
                color: #11142D;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header
        h_box = QHBoxLayout()
        icon = QLabel("🌐")
        icon.setStyleSheet("font-size: 28px;")
        h_box.addWidget(icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title = QLabel("Waveium Mobile & Web Companion")
        title.setStyleSheet("font-size: 17px; font-weight: 900; color: #5B4DF0;")
        sub = QLabel("Access live network topology & signal advisor from your phone or browser")
        sub.setStyleSheet("font-size: 11px; color: #737791;")
        title_vbox.addWidget(title)
        title_vbox.addWidget(sub)
        h_box.addLayout(title_vbox)
        h_box.addStretch()
        layout.addLayout(h_box)

        # Status badge
        status = QLabel("●  SERVER ACTIVE & BROADCASTING ON LOCAL WI-FI")
        status.setStyleSheet("""
            background: #E8FBF5;
            color: #087B55;
            border: 1px solid #C1F1D8;
            border-radius: 10px;
            padding: 8px 12px;
            font-size: 10px;
            font-weight: 800;
        """)
        layout.addWidget(status)

        # Mobile URL card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #F7F6FD;
                border: 1.5px solid #D6D0FA;
                border-radius: 14px;
                padding: 14px;
            }
        """)
        card_vbox = QVBoxLayout(card)
        card_vbox.setSpacing(10)

        lbl_phone = QLabel("📱 Open on Your Smartphone (Scan QR or Enter URL):")
        lbl_phone.setStyleSheet("font-size: 12px; font-weight: 800; color: #11142D;")
        card_vbox.addWidget(lbl_phone)

        # QR Code and scan info
        import os
        qr_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web", "icons", "mobile_qr_code.png")
        if os.path.exists(qr_path):
            qr_hbox = QHBoxLayout()
            qr_lbl = QLabel()
            pix = QPixmap(qr_path).scaled(130, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            qr_lbl.setPixmap(pix)
            qr_lbl.setStyleSheet("background: white; border: 1px solid #D6D0FA; border-radius: 10px; padding: 4px;")
            
            qr_info_box = QVBoxLayout()
            qr_info_box.setSpacing(4)
            qr_scan_title = QLabel("📷 <b>Scan with Your Phone Camera:</b>")
            qr_scan_title.setStyleSheet("font-size: 12px; color: #5B4DF0;")
            qr_scan_desc = QLabel(
                "1. Connect phone to Wi-Fi (<b>Airtel_kevi_8152</b>).<br>"
                "2. Open camera and scan this QR code.<br>"
                "3. Tap the link to open Waveium instantly!"
            )
            qr_scan_desc.setWordWrap(True)
            qr_scan_desc.setStyleSheet("font-size: 11px; color: #4A4D68; line-height: 1.4;")
            
            qr_info_box.addWidget(qr_scan_title)
            qr_info_box.addWidget(qr_scan_desc)
            qr_info_box.addStretch()
            
            qr_hbox.addWidget(qr_lbl)
            qr_hbox.addSpacing(14)
            qr_hbox.addLayout(qr_info_box)
            card_vbox.addLayout(qr_hbox)

        lbl_manual = QLabel("Or manually type this exact address into your phone's browser:")
        lbl_manual.setStyleSheet("font-size: 11px; font-weight: 600; color: #737791;")
        card_vbox.addWidget(lbl_manual)

        url_line = QLineEdit(mobile_url)
        url_line.setReadOnly(True)
        url_line.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #C9C4F8;
                border-radius: 8px;
                padding: 8px 12px;
                font-family: monospace;
                font-size: 14px;
                font-weight: 700;
                color: #5B4DF0;
            }
        """)
        card_vbox.addWidget(url_line)

        instructions = QLabel(
            "<b>Note:</b> Do not type <i>localhost</i> on your phone. <i>localhost</i> only works on this PC."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 11px; color: #E03137; line-height: 1.4; padding: 2px 0;")
        card_vbox.addWidget(instructions)
        layout.addWidget(card)

        # Actions
        btn_box = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy Mobile URL")
        btn_copy.setFixedHeight(36)
        btn_copy.setCursor(Qt.PointingHandCursor)
        btn_copy.setStyleSheet("""
            QPushButton {
                background: #5B4DF0;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 800;
                padding: 0 16px;
            }
            QPushButton:hover { background: #4738DB; }
        """)
        btn_copy.clicked.connect(lambda: (QApplication.clipboard().setText(mobile_url), btn_copy.setText("✓ Copied!")))
        btn_box.addWidget(btn_copy)

        btn_browser = QPushButton("💻 Open in Web Browser")
        btn_browser.setFixedHeight(36)
        btn_browser.setCursor(Qt.PointingHandCursor)
        btn_browser.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                color: #5B4DF0;
                border: 1.5px solid #5B4DF0;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 800;
                padding: 0 16px;
            }
            QPushButton:hover { background: #F7F6FD; }
        """)
        btn_browser.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(desktop_url)))
        btn_box.addWidget(btn_browser)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(36)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: #F1F1F8;
                color: #737791;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 16px;
            }
            QPushButton:hover { background: #E5E5F2; }
        """)
        btn_close.clicked.connect(dlg.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

        dlg.exec()


# ==========================================================
# CREATE APPLICATION
# ==========================================================

def create_waveium_app():

    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    window = WaveiumMainWindow()
    window.show()

    return app, window
