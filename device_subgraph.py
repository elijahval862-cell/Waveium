import networkx as nx


class DeviceSubgraph:

    @staticmethod
    def create(graph, device):

        subgraph = nx.Graph()

        if device not in graph.nodes:
            return subgraph

        data = graph.nodes[device]

        # Main device vertex
        subgraph.add_node(
            device,
            role="device",
            label=data.get(
                "label",
                str(device)
            ),
            vertex_type="device"
        )

        # --------------------------------------------------
        # Information vertices
        # --------------------------------------------------

        metrics = {
            "SIGNAL": data.get(
                "signal",
                "NOT MEASURED"
            ),

            "DISTANCE": data.get(
                "distance",
                "NOT ESTIMATED"
            ),

            "QUALITY": data.get(
                "quality",
                "NOT MEASURED"
            ),

            "RANGE": data.get(
                "range",
                "NOT ESTIMATED"
            ),

            "STATUS": data.get(
                "status",
                "UNKNOWN"
            ),

            "DEGREE": data.get(
                "degree",
                graph.degree(device)
            ),

            "CENTRALITY": data.get(
                "centrality",
                0.0
            )
        }

        # --------------------------------------------------
        # Create sub-vertices
        # --------------------------------------------------

        for metric, value in metrics.items():

            sub_node = (
                f"{device}_{metric}"
            )

            subgraph.add_node(
                sub_node,

                role="metric",

                metric=metric,

                value=value,

                vertex_type="sub_vertex"
            )

            subgraph.add_edge(
                device,
                sub_node,

                relation="metric"
            )

        return subgraph


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    print(
        "DeviceSubgraph module ready."
    )