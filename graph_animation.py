import matplotlib.pyplot as plt
import networkx as nx

from matplotlib.animation import FuncAnimation


class WaveiumGraphAnimation:

    def show(self, graph, title="WAVEIUM — Network Visualization"):

        # -------------------------------------------------
        # High-resolution figure
        # -------------------------------------------------

        fig, ax = plt.subplots(
            figsize=(14, 9),
            dpi=120
        )

        # -------------------------------------------------
        # Graph layout
        # -------------------------------------------------

        positions = nx.spring_layout(
            graph,
            seed=42,
            k=1.8
        )

        # -------------------------------------------------
        # Calculate signal values
        # -------------------------------------------------

        signals = []

        for _, _, data in graph.edges(data=True):

            signal = data.get("signal", -90)

            signals.append(signal)

        if signals:

            minimum_signal = min(signals)
            maximum_signal = max(signals)

        else:

            minimum_signal = -90
            maximum_signal = -30

        # -------------------------------------------------
        # Edge widths based on signal
        # -------------------------------------------------

        edge_widths = []

        for _, _, data in graph.edges(data=True):

            signal = data.get("signal", -90)

            if maximum_signal != minimum_signal:

                normalized = (
                    (signal - minimum_signal)
                    /
                    (maximum_signal - minimum_signal)
                )

            else:

                normalized = 0.5

            width = 1.5 + normalized * 5

            edge_widths.append(width)

        # -------------------------------------------------
        # Draw edges
        # -------------------------------------------------

        nx.draw_networkx_edges(
            graph,
            positions,
            ax=ax,
            width=edge_widths,
            alpha=0.65
        )

        # -------------------------------------------------
        # Draw nodes
        # -------------------------------------------------

        nx.draw_networkx_nodes(
            graph,
            positions,
            ax=ax,
            node_size=1500,
            node_color="black",
            edgecolors="white",
            linewidths=2
        )

        # -------------------------------------------------
        # Node labels
        # -------------------------------------------------

        nx.draw_networkx_labels(
            graph,
            positions,
            ax=ax,
            font_color="white",
            font_size=13,
            font_weight="bold"
        )

        # -------------------------------------------------
        # Edge information
        # -------------------------------------------------

        edge_labels = {}

        for u, v, data in graph.edges(data=True):

            signal = data.get("signal", "N/A")
            range_value = data.get("range", "N/A")

            edge_labels[(u, v)] = (
                f"{signal} dBm\n"
                f"Range {range_value}"
            )

        nx.draw_networkx_edge_labels(
            graph,
            positions,
            edge_labels=edge_labels,
            ax=ax,
            font_size=8
        )

        # -------------------------------------------------
        # Signal particles
        # -------------------------------------------------

        particles = []

        for u, v in graph.edges():

            particle, = ax.plot(
                [],
                [],
                marker="o",
                markersize=8,
                markeredgewidth=1
            )

            particles.append(
                {
                    "particle": particle,
                    "u": u,
                    "v": v
                }
            )

        # -------------------------------------------------
        # Animation
        # -------------------------------------------------

        def update(frame):

            progress = (frame % 120) / 120

            for item in particles:

                u = item["u"]
                v = item["v"]

                x1, y1 = positions[u]
                x2, y2 = positions[v]

                x = x1 + (x2 - x1) * progress
                y = y1 + (y2 - y1) * progress

                item["particle"].set_data(
                    [x],
                    [y]
                )

            return [
                item["particle"]
                for item in particles
            ]

        animation = FuncAnimation(
            fig,
            update,
            frames=120,
            interval=30,
            blit=False,
            repeat=True
        )

        # -------------------------------------------------
        # Title
        # -------------------------------------------------

        ax.set_title(
            title,
            fontsize=20,
            fontweight="bold",
            pad=20
        )

        # -------------------------------------------------
        # Information panel
        # -------------------------------------------------

        vertices = graph.number_of_nodes()
        edges = graph.number_of_edges()

        if vertices > 0:

            connected = nx.is_connected(graph)

        else:

            connected = False

        information = (
            f"Vertices: {vertices}    "
            f"Edges: {edges}    "
            f"Connected: {'YES' if connected else 'NO'}"
        )

        ax.text(
            0.5,
            -0.04,
            information,
            transform=ax.transAxes,
            ha="center",
            fontsize=11
        )

        # -------------------------------------------------
        # Clean display
        # -------------------------------------------------

        ax.axis("off")

        fig.patch.set_facecolor("black")
        ax.set_facecolor("black")

        plt.tight_layout()

        plt.show()