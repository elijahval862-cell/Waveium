import networkx as nx


class WaveiumGraph:
    """
    Core graph engine for Waveium.

    Represents a network as:

        G = (V, E, W)

    V = vertices
    E = edges
    W = edge weights / signal values
    """

    def __init__(self):
        self.graph = nx.Graph()

    # -----------------------------
    # Vertex operations
    # -----------------------------

    def add_vertex(self, vertex):
        self.graph.add_node(vertex)

    def remove_vertex(self, vertex):
        if vertex in self.graph:
            self.graph.remove_node(vertex)

    # -----------------------------
    # Edge operations
    # -----------------------------

    def add_edge(self, u, v, signal=None, range_value=None):
        self.graph.add_edge(
            u,
            v,
            signal=signal,
            range=range_value
        )

    def remove_edge(self, u, v):
        if self.graph.has_edge(u, v):
            self.graph.remove_edge(u, v)

    # -----------------------------
    # Graph properties
    # -----------------------------

    def number_of_vertices(self):
        return self.graph.number_of_nodes()

    def number_of_edges(self):
        return self.graph.number_of_edges()

    def degree(self, vertex):
        return self.graph.degree(vertex)

    def neighbors(self, vertex):
        return list(self.graph.neighbors(vertex))

    def is_connected(self):
        if self.number_of_vertices() == 0:
            return False

        return nx.is_connected(self.graph)

    # -----------------------------
    # Display information
    # -----------------------------

    def information(self):

        print("\n========== WAVEIUM GRAPH ==========")

        print("Vertices :", self.number_of_vertices())
        print("Edges    :", self.number_of_edges())

        print("\nDegree:")

        for vertex, degree in self.graph.degree():
            print(f"  {vertex}: {degree}")

        print("\nEdges:")

        for u, v, data in self.graph.edges(data=True):

            signal = data.get("signal")
            range_value = data.get("range")

            print(
                f"  {u} -- {v} | "
                f"Signal: {signal} | "
                f"Range: {range_value}"
            )

        print("\nConnected:", self.is_connected())