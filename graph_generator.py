import math
import networkx as nx


class WaveiumGraphGenerator:

    # ==========================================================
    # BASIC GRAPH GENERATORS
    # ==========================================================

    @staticmethod
    def complete_graph(n):
        return nx.complete_graph(n)

    @staticmethod
    def path_graph(n):
        return nx.path_graph(n)

    @staticmethod
    def cycle_graph(n):
        return nx.cycle_graph(n)

    @staticmethod
    def star_graph(n):
        return nx.star_graph(n)

    @staticmethod
    def wheel_graph(n):
        return nx.wheel_graph(n)

    @staticmethod
    def complete_bipartite_graph(n, m):
        return nx.complete_bipartite_graph(n, m)

    # ==========================================================
    # SIGNAL / NETWORK METRICS
    # ==========================================================

    @staticmethod
    def signal_quality(rssi):

        if rssi is None:
            return "UNKNOWN"

        if rssi >= -50:
            return "EXCELLENT"

        if rssi >= -60:
            return "GOOD"

        if rssi >= -70:
            return "FAIR"

        if rssi >= -80:
            return "WEAK"

        return "POOR"

    @staticmethod
    def estimate_distance(
        rssi,
        tx_power=-40,
        path_loss_exponent=2.7
    ):

        if rssi is None:
            return None

        try:
            distance = 10 ** (
                (tx_power - float(rssi))
                / (10 * path_loss_exponent)
            )

            return round(
                max(distance, 0.1),
                2
            )

        except (
            TypeError,
            ValueError,
            ZeroDivisionError
        ):
            return None

    @staticmethod
    def estimate_router_coverage(band=None, current_rssi=None, current_distance=None):
        """
        Estimates the router's overall Wi-Fi signal coverage radius,
        usable area, and zone boundaries based on RF propagation models.
        """
        is_5g = False
        if band:
            is_5g = ("5" in str(band))

        n = 2.7 if is_5g else 2.3
        p0 = -40.0  # reference at 1m

        if current_rssi is not None and current_distance is not None:
            try:
                r_val = float(current_rssi)
                d_val = float(current_distance)
                if d_val > 0.5 and r_val < p0:
                    calib_n = (p0 - r_val) / (10 * math.log10(d_val))
                    if 1.8 <= calib_n <= 3.8:
                        n = calib_n
            except Exception:
                pass

        # Compute zone boundary distances in meters with realistic indoor limits
        if is_5g:
            d_core = max(1.8, min(3.2, 10 ** ((p0 - (-50.0)) / (10 * n))))
            d_strong = max(5.0, min(9.0, 10 ** ((p0 - (-60.0)) / (10 * n))))
            d_good = max(11.0, min(16.5, 10 ** ((p0 - (-70.0)) / (10 * n))))
            d_fair = max(18.0, min(25.0, 10 ** ((p0 - (-80.0)) / (10 * n))))
            d_max = max(26.0, min(35.0, 10 ** ((p0 - (-85.0)) / (10 * n))))
        else:
            d_core = max(2.2, min(4.0, 10 ** ((p0 - (-50.0)) / (10 * n))))
            d_strong = max(7.0, min(12.0, 10 ** ((p0 - (-60.0)) / (10 * n))))
            d_good = max(15.0, min(22.0, 10 ** ((p0 - (-70.0)) / (10 * n))))
            d_fair = max(25.0, min(36.0, 10 ** ((p0 - (-80.0)) / (10 * n))))
            d_max = max(38.0, min(50.0, 10 ** ((p0 - (-85.0)) / (10 * n))))

        area_sqm = round(math.pi * (min(d_fair, 32.0) ** 2) * 0.65)
        area_sqft = round(area_sqm * 10.7639)

        return {
            "max_distance": round(d_max, 1),
            "fair_distance": round(d_fair, 1),
            "good_distance": round(d_good, 1),
            "strong_distance": round(d_strong, 1),
            "core_distance": round(d_core, 1),
            "area_sqm": area_sqm,
            "area_sqft": area_sqft,
            "band": "5 GHz" if is_5g else ("2.4 GHz" if band else "Standard Wi-Fi"),
            "path_loss_exponent": round(n, 2)
        }

    @staticmethod
    def connection_status(rssi):

        if rssi is None:
            return "UNKNOWN"

        if rssi >= -60:
            return "STABLE"

        if rssi >= -70:
            return "MODERATE"

        if rssi >= -80:
            return "WEAK"

        return "UNSTABLE"

    # ==========================================================
    # LATENCY HELPERS
    # ==========================================================

    @staticmethod
    def latency_quality(latency_ms):

        if latency_ms is None:
            return "NOT MEASURED"

        try:
            latency_ms = float(latency_ms)
        except (
            TypeError,
            ValueError
        ):
            return "NOT MEASURED"

        if latency_ms < 10:
            return "EXCELLENT"

        if latency_ms < 30:
            return "GOOD"

        if latency_ms < 60:
            return "FAIR"

        if latency_ms < 100:
            return "WEAK"

        return "POOR"

    @staticmethod
    def latency_status(latency_ms):

        if latency_ms is None:
            return "NOT MEASURED"

        try:
            latency_ms = float(latency_ms)
        except (
            TypeError,
            ValueError
        ):
            return "NOT MEASURED"

        if latency_ms < 30:
            return "LOW"

        if latency_ms < 60:
            return "MODERATE"

        if latency_ms < 100:
            return "HIGH"

        return "VERY HIGH"

    # ==========================================================
    # BUILD NETWORK FROM SCANNER DATA
    # ==========================================================

    @staticmethod
    def build_network(scanner_data):

        graph = nx.Graph()

        if not scanner_data:
            return graph

        gateway = scanner_data.get(
            "gateway"
        )

        local_ip = scanner_data.get(
            "local_ip"
        )

        devices = scanner_data.get(
            "devices",
            []
        )

        wifi = scanner_data.get(
            "wifi",
            {}
        )

        router_station_count = scanner_data.get(
            "router_station_count",
            len(devices)
        )

        # ------------------------------------------------------
        # ROUTER
        # ------------------------------------------------------

        if gateway:

            router_rssi = wifi.get(
                "rssi"
            )

            graph.add_node(
                gateway,
                role="router",
                label="Router",
                ip=gateway,
                mac=wifi.get("bssid"),
                rssi=router_rssi,
                signal=wifi.get(
                    "signal_percent"
                ),
                signal_quality=WaveiumGraphGenerator.signal_quality(
                    router_rssi
                ),
                distance=0.0,
                status="ROUTER",
                latency_ms=None,
                latency_quality="NOT MEASURED",
                latency_status="NOT MEASURED",
                station_count=router_station_count
            )

        # ------------------------------------------------------
        # LOCAL COMPUTER
        # ------------------------------------------------------

        if local_ip:

            local_rssi = wifi.get(
                "rssi"
            )

            graph.add_node(
                local_ip,
                role="local_device",
                label="This Device",
                ip=local_ip,
                mac=None,
                rssi=local_rssi,
                signal=wifi.get(
                    "signal_percent"
                ),
                signal_quality=WaveiumGraphGenerator.signal_quality(
                    local_rssi
                ),
                distance=0.0,
                status="LOCAL",
                latency_ms=None,
                latency_quality="NOT MEASURED",
                latency_status="NOT MEASURED",
                station_source="LOCAL COMPUTER"
            )

            # Router -> local computer
            if gateway and gateway != local_ip:

                graph.add_edge(
                    gateway,
                    local_ip,
                    rssi=local_rssi,
                    signal=wifi.get(
                        "signal_percent"
                    ),
                    distance=0.0,
                    signal_quality=WaveiumGraphGenerator.signal_quality(
                        local_rssi
                    ),
                    status="LOCAL CONNECTION",
                    latency_ms=None,
                    latency_quality="NOT MEASURED",
                    latency_status="NOT MEASURED",
                    connection="LOCAL NETWORK"
                )

        # ------------------------------------------------------
        # DISCOVERED DEVICES
        # ------------------------------------------------------

        for device in devices:

            ip = device.get(
                "ip"
            )

            if not ip:
                continue

            # Avoid duplicating the local machine or router.
            if ip == local_ip or ip == gateway:
                continue

            rssi = device.get(
                "rssi"
            )

            signal = device.get(
                "signal"
            )

            # Remote-device RSSI is intentionally NOT inferred.
            quality = (
                device.get(
                    "signal_quality"
                )
                or WaveiumGraphGenerator.signal_quality(
                    rssi
                )
            )

            distance = device.get(
                "distance"
            )

            if distance is None and rssi is not None:
                distance = WaveiumGraphGenerator.estimate_distance(
                    rssi
                )

            latency_ms = device.get(
                "latency_ms"
            )

            latency_quality = (
                device.get(
                    "latency_quality"
                )
                or WaveiumGraphGenerator.latency_quality(
                    latency_ms
                )
            )

            latency_status = (
                device.get(
                    "latency_status"
                )
                or WaveiumGraphGenerator.latency_status(
                    latency_ms
                )
            )

            status = device.get(
                "status",
                "ACTIVE"
            )

            graph.add_node(
                ip,
                role="device",
                label=device.get(
                    "hostname",
                    ip
                ),
                ip=ip,
                mac=device.get(
                    "mac"
                ),
                device_type=device.get(
                    "type",
                    "unknown"
                ),
                rssi=rssi,
                signal=signal,
                signal_quality=quality,
                distance=distance,
                status=status,

                # REAL latency from NetworkDiscovery.
                latency_ms=latency_ms,
                latency_quality=latency_quality,
                latency_status=latency_status,

                station_source=device.get(
                    "station_source",
                    "PC DISCOVERY"
                )
            )

            # Router -> discovered device.
            if gateway:

                graph.add_edge(
                    gateway,
                    ip,
                    rssi=rssi,
                    signal=signal,
                    distance=distance,
                    signal_quality=quality,
                    status=status,

                    # REAL latency from NetworkDiscovery.
                    latency_ms=latency_ms,
                    latency_quality=latency_quality,
                    latency_status=latency_status,

                    connection="LOCAL NETWORK"
                )

        # ------------------------------------------------------
        # GRAPH METRICS
        # ------------------------------------------------------

        if graph.number_of_nodes() > 0:

            degree_centrality = nx.degree_centrality(
                graph
            )

            for node in graph.nodes:

                graph.nodes[node][
                    "degree"
                ] = graph.degree(node)

                graph.nodes[node][
                    "centrality"
                ] = round(
                    degree_centrality.get(
                        node,
                        0.0
                    ),
                    4
                )

        if graph.number_of_nodes() > 0:

            highest_degree_node = max(
                graph.nodes,
                key=lambda node:
                    graph.degree(node)
            )

            graph.graph[
                "highest_degree"
            ] = highest_degree_node

        graph.graph[
            "gateway"
        ] = gateway

        graph.graph[
            "local_ip"
        ] = local_ip

        graph.graph[
            "latency_summary"
        ] = scanner_data.get(
            "latency_summary",
            {}
        )

        graph.graph[
            "wifi"
        ] = wifi

        return graph

    # ==========================================================
    # PREPARE NETWORK
    # ==========================================================

    @staticmethod
    def prepare_network(graph):

        if graph is None:
            return nx.Graph()

        prepared = graph.copy()

        for node in prepared.nodes:

            prepared.nodes[node].setdefault(
                "degree",
                prepared.degree(node)
            )

            prepared.nodes[node].setdefault(
                "centrality",
                0.0
            )

            prepared.nodes[node].setdefault(
                "latency_ms",
                None
            )

            prepared.nodes[node].setdefault(
                "latency_quality",
                "NOT MEASURED"
            )

            prepared.nodes[node].setdefault(
                "latency_status",
                "NOT MEASURED"
            )

        for u, v in prepared.edges:

            prepared.edges[u, v].setdefault(
                "latency_ms",
                None
            )

            prepared.edges[u, v].setdefault(
                "latency_quality",
                "NOT MEASURED"
            )

            prepared.edges[u, v].setdefault(
                "latency_status",
                "NOT MEASURED"
            )

        return prepared

    # ==========================================================
    # NETWORK SUMMARY
    # ==========================================================

    @staticmethod
    def network_summary(graph):

        if graph is None:
            return {
                "nodes": 0,
                "edges": 0,
                "devices": 0,
                "average_latency_ms": None,
                "min_latency_ms": None,
                "max_latency_ms": None
            }

        latencies = []

        for node in graph.nodes:

            latency = graph.nodes[node].get(
                "latency_ms"
            )

            if latency is not None:

                try:
                    latencies.append(
                        float(latency)
                    )
                except (
                    TypeError,
                    ValueError
                ):
                    pass

        summary = {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "devices": sum(
                1
                for node in graph.nodes
                if graph.nodes[node].get(
                    "role"
                ) == "device"
            ),
            "average_latency_ms": None,
            "min_latency_ms": None,
            "max_latency_ms": None
        }

        if latencies:

            summary[
                "average_latency_ms"
            ] = round(
                sum(latencies)
                / len(latencies),
                2
            )

            summary[
                "min_latency_ms"
            ] = round(
                min(latencies),
                2
            )

            summary[
                "max_latency_ms"
            ] = round(
                max(latencies),
                2
            )

        return summary


# ==========================================================
# SIMPLE TEST
# ==========================================================

if __name__ == "__main__":

    test_data = {
        "gateway": "192.168.1.1",
        "local_ip": "192.168.1.3",
        "devices": [
            {
                "ip": "192.168.1.2",
                "mac": "34-b9-8d-bd-66-ab",
                "latency_ms": 30,
                "latency_quality": "FAIR"
            },
            {
                "ip": "192.168.1.4",
                "mac": "36-93-f7-0c-e0-6a",
                "latency_ms": 8,
                "latency_quality": "EXCELLENT"
            },
            {
                "ip": "192.168.1.5",
                "mac": "d2-31-99-e9-aa-4d",
                "latency_ms": 7,
                "latency_quality": "EXCELLENT"
            },
            {
                "ip": "192.168.1.6",
                "mac": "2e-10-90-ba-a6-54",
                "latency_ms": 234,
                "latency_quality": "POOR"
            }
        ],
        "wifi": {
            "signal_percent": 100,
            "rssi": -50
        },
        "latency_summary": {
            "average_ms": 69.75,
            "min_ms": 7,
            "max_ms": 234,
            "measured_devices": 4
        }
    }

    graph = WaveiumGraphGenerator.build_network(
        test_data
    )

    print("=" * 60)
    print("WAVEIUM GRAPH GENERATOR TEST")
    print("=" * 60)

    print(
        f"Nodes : {graph.number_of_nodes()}"
    )

    print(
        f"Edges : {graph.number_of_edges()}"
    )

    print()

    for node in graph.nodes:

        data = graph.nodes[node]

        if data.get("role") == "device":

            print(
                f"{node:<16} "
                f"Latency: "
                f"{data.get('latency_ms')} ms   "
                f"Quality: "
                f"{data.get('latency_quality')}"
            )

    print()

    print(
        "Summary:",
        WaveiumGraphGenerator.network_summary(
            graph
        )
    )
