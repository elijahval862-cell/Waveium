import matplotlib.pyplot as plt
import networkx as nx


class WaveiumGraphView:

    def show(self, graph, title="Waveium Network"):

        plt.figure(figsize=(10, 7))

        positions = nx.spring_layout(
            graph,
            seed=42
        )

        nx.draw_networkx_nodes(
            graph,
            positions,
            node_size=900
        )

        nx.draw_networkx_edges(
            graph,
            positions,
            width=2
        )

        nx.draw_networkx_labels(
            graph,
            positions,
            font_size=12
        )

        edge_labels = {}

        for u, v, data in graph.edges(data=True):

            signal = data.get("signal", "N/A")
            range_value = data.get("range", "N/A")

            edge_labels[(u, v)] = (
                f"S:{signal} dBm\n"
                f"R:{range_value}"
            )

        nx.draw_networkx_edge_labels(
            graph,
            positions,
            edge_labels=edge_labels,
            font_size=8
        )

        plt.title(title)

        plt.axis("off")

        plt.tight_layout()

        plt.show()