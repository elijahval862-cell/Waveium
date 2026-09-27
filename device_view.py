class DeviceView:

    def __init__(self, graph):

        self.graph = graph
        self.selected_device = None
        self.expanded = False

    # ==================================================
    # SELECT DEVICE
    # ==================================================

    def select_device(self, device):

        if device not in self.graph.nodes:
            return False

        data = self.graph.nodes[device]

        if data.get("role") != "device":
            return False

        self.selected_device = device
        self.expanded = True

        return True

    # ==================================================
    # CLOSE DEVICE DETAILS
    # ==================================================

    def collapse(self):

        self.selected_device = None
        self.expanded = False

    # ==================================================
    # IS EXPANDED?
    # ==================================================

    def is_expanded(self):

        return (
            self.expanded
            and self.selected_device is not None
        )

    # ==================================================
    # GET DEVICE DATA
    # ==================================================

    def get_metrics(self):

        if not self.is_expanded():
            return {}

        data = self.graph.nodes[
            self.selected_device
        ]

        return {

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
                0
            ),

            "CENTRALITY": data.get(
                "centrality",
                0.0
            )
        }


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    print(
        "DeviceView module ready."
    )