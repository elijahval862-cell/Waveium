import networkx as nx

from core.network_discovery import NetworkDiscovery
from core.device_metrics import DeviceMetrics


class NetworkTopology:

    def __init__(self):

        self.discovery = NetworkDiscovery()

    # ==================================================
    # BUILD REAL NETWORK GRAPH
    # ==================================================

    def build_graph(self):

        network = self.discovery.discover()

        gateway = network.get(
            "gateway"
        )

        devices = network.get(
            "devices",
            []
        )

        graph = nx.Graph()

        # ==================================================
        # ROUTER
        # ==================================================

        if gateway:

            graph.add_node(
                gateway,

                role="router",

                label="ROUTER",

                ip=gateway
            )

        # ==================================================
        # DEVICES
        # ==================================================

        device_number = 1

        for device in devices:

            ip = device.get(
                "ip"
            )

            if not ip:
                continue

            # Don't add router as a device

            if ip == gateway:
                continue

            device_name = (
                f"DEVICE {device_number:02d}"
            )

            graph.add_node(

                ip,

                role="device",

                label=device_name,

                ip=ip,

                mac=device.get(
                    "mac"
                ),

                device_number=device_number
            )

            # ==================================================
            # ROUTER → DEVICE CONNECTION
            # ==================================================

            if gateway:

                graph.add_edge(

                    gateway,

                    ip,

                    signal=None,

                    quality="UNKNOWN",

                    distance=None,

                    range=None,

                    status="UNKNOWN",

                    connection="Wi-Fi/LAN"
                )

            device_number += 1

        # ==================================================
        # DEGREE
        # ==================================================

        degrees = {
            node: graph.degree(node)
            for node in graph.nodes()
        }

        # ==================================================
        # DEGREE CENTRALITY
        # ==================================================

        if graph.number_of_nodes() > 1:

            centrality = (
                nx.degree_centrality(
                    graph
                )
            )

        else:

            centrality = {
                node: 0.0
                for node in graph.nodes()
            }

        # ==================================================
        # ADD DEGREE/CENTRALITY TO NODES
        # ==================================================

        for node in graph.nodes():

            graph.nodes[node][
                "degree"
            ] = degrees.get(
                node,
                0
            )

            graph.nodes[node][
                "centrality"
            ] = round(
                centrality.get(
                    node,
                    0.0
                ),
                3
            )

        # ==================================================
        # ADD METRIC PLACEHOLDERS TO EDGES
        # ==================================================

        for u, v, data in graph.edges(
            data=True
        ):

            signal = data.get(
                "signal"
            )

            # At this stage we only calculate
            # metrics when a real RSSI exists.
            #
            # We deliberately DO NOT invent
            # RSSI values for other devices.

            if signal is not None:

                metrics = (
                    DeviceMetrics.calculate(
                        signal,
                        degree=graph.degree(v),
                        centrality=centrality.get(
                            v,
                            0.0
                        )
                    )
                )

                data.update(
                    metrics
                )

            else:

                data["quality"] = (
                    "NOT MEASURED"
                )

                data["distance"] = None

                data["range"] = None

                data["status"] = (
                    "CONNECTED"
                )

        return graph

    # ==================================================
    # FIND ROUTER
    # ==================================================

    @staticmethod
    def get_router(graph):

        for node, data in graph.nodes(
            data=True
        ):

            if data.get(
                "role"
            ) == "router":

                return node

        return None

    # ==================================================
    # GET DEGREES
    # ==================================================

    @staticmethod
    def get_degrees(graph):

        return {
            node: graph.degree(node)
            for node in graph.nodes()
        }

    # ==================================================
    # GET CENTRALITY
    # ==================================================

    @staticmethod
    def get_degree_centrality(graph):

        if graph.number_of_nodes() <= 1:

            return {
                node: 0.0
                for node in graph.nodes()
            }

        return nx.degree_centrality(
            graph
        )


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    print("=" * 65)

    print(
        "       WAVEIUM NETWORK TOPOLOGY"
    )

    print("=" * 65)

    topology = NetworkTopology()

    graph = topology.build_graph()

    print()

    # ==================================================
    # VERTICES
    # ==================================================

    print("VERTICES")

    print("-" * 65)

    for node, data in graph.nodes(
        data=True
    ):

        print(
            f"{data.get('label', node):<15}"
            f" IP: {node:<18}"
            f" Degree: {data.get('degree', 0):<3}"
            f" Centrality: "
            f"{data.get('centrality', 0):.3f}"
        )

    print()

    # ==================================================
    # EDGES
    # ==================================================

    print("CONNECTIONS")

    print("-" * 65)

    for u, v, data in graph.edges(
        data=True
    ):

        print(
            f"{u}  ─────  {v}"
        )

        print(
            f"  Signal   : "
            f"{data.get('signal')}"
        )

        print(
            f"  Quality  : "
            f"{data.get('quality')}"
        )

        print(
            f"  Distance : "
            f"{data.get('distance')}"
        )

        print(
            f"  Range    : "
            f"{data.get('range')}"
        )

        print(
            f"  Status   : "
            f"{data.get('status')}"
        )

        print()

    # ==================================================
    # SUMMARY
    # ==================================================

    router = topology.get_router(
        graph
    )

    print("=" * 65)

    print(
        f"ROUTER: {router}"
    )

    print(
        f"VERTICES: "
        f"{graph.number_of_nodes()}"
    )

    print(
        f"EDGES: "
        f"{graph.number_of_edges()}"
    )

    print("=" * 65)