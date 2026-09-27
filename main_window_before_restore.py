import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)

from PySide6.QtCore import Qt

from core.network_scanner import NetworkScanner
from core.graph_generator import WaveiumGraphGenerator
from ui.graph_canvas import WaveiumGraphCanvas


class WaveiumMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "WAVEIUM - Network Connectivity Visualizer"
        )

        self.resize(1400, 800)

        self.graph = None

        # ==========================================
        # CENTRAL WIDGET
        # ==========================================

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # ==========================================
        # LEFT PANEL
        # ==========================================

        left_panel = QWidget()

        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)

        left_panel.setMaximumWidth(330)

        # ==========================================
        # TITLE
        # ==========================================

        title = QLabel("WAVEIUM")

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setStyleSheet("""
            QLabel {
                font-size: 30px;
                font-weight: bold;
                padding: 15px;
            }
        """)

        left_layout.addWidget(title)

        subtitle = QLabel(
            "Network Connectivity Visualizer"
        )

        subtitle.setAlignment(
            Qt.AlignCenter
        )

        subtitle.setWordWrap(True)

        left_layout.addWidget(subtitle)

        # ==========================================
        # SCAN BUTTON
        # ==========================================

        self.scan_button = QPushButton(
            "SCAN NETWORK"
        )

        self.scan_button.setMinimumHeight(50)

        self.scan_button.clicked.connect(
            self.scan_network
        )

        left_layout.addWidget(
            self.scan_button
        )

        # ==========================================
        # OUTPUT
        # ==========================================

        self.output = QTextEdit()

        self.output.setReadOnly(True)

        self.output.setPlaceholderText(
            "Network information will appear here..."
        )

        left_layout.addWidget(
            self.output
        )

        # ==========================================
        # STATUS
        # ==========================================

        self.status = QLabel(
            "Ready"
        )

        self.status.setWordWrap(True)

        self.status.setAlignment(
            Qt.AlignCenter
        )

        left_layout.addWidget(
            self.status
        )

        # ==========================================
        # ADD LEFT PANEL
        # ==========================================

        main_layout.addWidget(
            left_panel
        )

        # ==========================================
        # RIGHT PANEL
        # ==========================================

        right_panel = QWidget()

        right_layout = QVBoxLayout()
        right_panel.setLayout(
            right_layout
        )

        # ==========================================
        # GRAPH TITLE
        # ==========================================

        graph_title = QLabel(
            "Network Topology"
        )

        graph_title.setAlignment(
            Qt.AlignCenter
        )

        graph_title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                padding: 10px;
            }
        """)

        right_layout.addWidget(
            graph_title
        )

        # ==========================================
        # GRAPH CANVAS
        # ==========================================

        self.canvas = WaveiumGraphCanvas()

        right_layout.addWidget(
            self.canvas
        )

        # ==========================================
        # DEVICE SELECTION
        # ==========================================

        self.canvas.device_selected.connect(
            self.device_selected
        )

        # ==========================================
        # ADD RIGHT PANEL
        # ==========================================

        main_layout.addWidget(
            right_panel
        )

        main_layout.setStretch(
            0,
            0
        )

        main_layout.setStretch(
            1,
            1
        )

    # ==============================================
    # SCAN NETWORK
    # ==============================================

    def scan_network(self):

        self.scan_button.setEnabled(
            False
        )

        self.status.setText(
            "Scanning network..."
        )

        self.output.clear()

        QApplication.processEvents()

        try:

            # --------------------------------------
            # 1. CREATE NETWORK SCANNER
            # --------------------------------------

            scanner = NetworkScanner()

            # --------------------------------------
            # 2. DISCOVER NETWORK
            # --------------------------------------

            scanner_data = scanner.scan()

            # --------------------------------------
            # 3. BUILD GRAPH
            # --------------------------------------

            self.graph = (
                WaveiumGraphGenerator
                .build_network(
                    scanner_data
                )
            )

            # --------------------------------------
            # 4. PREPARE GRAPH
            # --------------------------------------

            self.graph = (
                WaveiumGraphGenerator
                .prepare_network(
                    self.graph
                )
            )

            # --------------------------------------
            # 5. SEND GRAPH TO CANVAS
            # --------------------------------------

            self.canvas.set_graph(
                self.graph
            )

            # --------------------------------------
            # 6. SUMMARY
            # --------------------------------------

            summary = (
                WaveiumGraphGenerator
                .network_summary(
                    self.graph
                )
            )

            # ======================================
            # DISPLAY NETWORK INFORMATION
            # ======================================

            wifi = scanner_data.get(
                "wifi",
                {}
            )

            text = ""

            text += (
                "================================\n"
            )

            text += (
                "       WAVEIUM NETWORK SCAN\n"
            )

            text += (
                "================================\n\n"
            )

            text += (
                f"Local IP     : "
                f"{scanner_data.get('local_ip')}\n"
            )

            text += (
                f"Gateway      : "
                f"{scanner_data.get('gateway')}\n"
            )

            text += (
                f"Wi-Fi SSID   : "
                f"{wifi.get('ssid')}\n"
            )

            text += (
                f"Wi-Fi Signal : "
                f"{wifi.get('signal_percent')}%\n"
            )

            text += "\n"

            text += (
                "--------------------------------\n"
            )

            text += "GRAPH SUMMARY\n"

            text += (
                "--------------------------------\n"
            )

            text += (
                f"Vertices     : "
                f"{summary['vertices']}\n"
            )

            text += (
                f"Connections  : "
                f"{summary['edges']}\n"
            )

            text += (
                f"Router       : "
                f"{summary['router']}\n"
            )

            text += (
                f"Router Degree: "
                f"{summary['router_degree']}\n"
            )

            text += (
                f"Devices      : "
                f"{summary['confirmed_devices']}\n"
            )

            text += (
                f"Unknown      : "
                f"{summary['unknown_stations']}\n"
            )

            text += "\n"

            text += (
                "--------------------------------\n"
            )

            text += "DISCOVERED DEVICES\n"

            text += (
                "--------------------------------\n"
            )

            # ======================================
            # DEVICE DETAILS
            # ======================================

            for node, data in self.graph.nodes(
                data=True
            ):

                text += "\n"

                text += (
                    f"Device: "
                    f"{data.get('label', node)}\n"
                )

                text += (
                    f"  IP       : "
                    f"{data.get('ip')}\n"
                )

                text += (
                    f"  MAC      : "
                    f"{data.get('mac')}\n"
                )

                text += (
                    f"  Role     : "
                    f"{data.get('role')}\n"
                )

                text += (
                    f"  Status   : "
                    f"{data.get('status')}\n"
                )

                text += (
                    f"  Signal   : "
                    f"{data.get('signal')}\n"
                )

                text += (
                    f"  RSSI     : "
                    f"{data.get('rssi')}\n"
                )

                text += (
                    f"  Quality  : "
                    f"{data.get('quality')}\n"
                )

                text += (
                    f"  Distance : "
                    f"{data.get('distance')}\n"
                )

            self.output.setText(
                text
            )

            self.status.setText(
                "Network scan completed."
            )

        except Exception as error:

            self.status.setText(
                "Network scan failed."
            )

            self.output.setText(
                "ERROR\n"
                "================================\n\n"
                f"{type(error).__name__}\n\n"
                f"{error}\n"
            )

        finally:

            self.scan_button.setEnabled(
                True
            )

    # ==============================================
    # DEVICE SELECTED
    # ==============================================

    def device_selected(
        self,
        node
    ):

        if self.graph is None:
            return

        if node not in self.graph.nodes:
            return

        data = self.graph.nodes[node]

        information = (
            f"DEVICE INFORMATION\n"
            f"==============================\n\n"
            f"Name: {data.get('label', node)}\n"
            f"IP: {data.get('ip')}\n"
            f"MAC: {data.get('mac')}\n"
            f"Role: {data.get('role')}\n"
            f"Status: {data.get('status')}\n"
            f"Signal: {data.get('signal')}\n"
            f"RSSI: {data.get('rssi')}\n"
            f"Quality: {data.get('quality')}\n"
            f"Distance: {data.get('distance')}\n"
            f"Degree: {data.get('degree')}\n"
        )

        self.output.setText(
            information
        )


# ==============================================
# CREATE APPLICATION
# ==============================================

def create_waveium_app():

    app = QApplication.instance()

    if app is None:

        app = QApplication(
            sys.argv
        )

    window = WaveiumMainWindow()

    window.show()

    return app, window


# ==============================================
# RUN DIRECTLY
# ==============================================

if __name__ == "__main__":

    app, window = create_waveium_app()

    sys.exit(
        app.exec()
    )