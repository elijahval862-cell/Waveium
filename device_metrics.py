import math


class DeviceMetrics:

    # ==================================================
    # SIGNAL THRESHOLDS
    # ==================================================

    EXCELLENT = -50
    GOOD = -60
    FAIR = -70
    WEAK = -80

    # ==================================================
    # DISTANCE MODEL
    # ==================================================

    # Approximate RSSI at 1 metre
    REFERENCE_RSSI = -40

    # Path-loss exponent
    #
    # 2.0  -> open indoor environment
    # 2.2  -> typical indoor estimate
    # 3.0+ -> walls / difficult environment

    PATH_LOSS_EXPONENT = 2.2

    # ==================================================
    # SIGNAL QUALITY
    # ==================================================

    @classmethod
    def signal_quality(cls, rssi):

        if rssi is None:
            return "UNKNOWN"

        rssi = float(rssi)

        if rssi >= cls.EXCELLENT:
            return "EXCELLENT"

        if rssi >= cls.GOOD:
            return "GOOD"

        if rssi >= cls.FAIR:
            return "FAIR"

        if rssi >= cls.WEAK:
            return "WEAK"

        return "POOR"

    # ==================================================
    # ESTIMATED DISTANCE
    # ==================================================

    @classmethod
    def estimate_distance(cls, rssi):

        if rssi is None:
            return None

        rssi = float(rssi)

        distance = 10 ** (
            (
                cls.REFERENCE_RSSI - rssi
            )
            /
            (
                10 * cls.PATH_LOSS_EXPONENT
            )
        )

        return round(
            distance,
            2
        )

    # ==================================================
    # ESTIMATED USABLE RANGE
    # ==================================================

    @classmethod
    def estimate_range(cls):

        # Use FAIR (-70 dBm) as the
        # approximate usable threshold.

        return round(
            cls.estimate_distance(
                cls.FAIR
            ),
            2
        )

    # ==================================================
    # ESTIMATED ROUTER SIGNAL COVERAGE
    # ==================================================

    @classmethod
    def estimate_router_coverage(
        cls,
        band=None,
        current_rssi=None,
        current_distance=None
    ):
        """
        Estimates the router's overall Wi-Fi signal coverage radius,
        usable area, and zone boundaries based on RF propagation models.
        """
        is_5g = False
        if band:
            is_5g = ("5" in str(band))

        # Path loss exponent: ~2.7 for 5 GHz indoors, ~2.3 for 2.4 GHz indoors
        n = 2.7 if is_5g else 2.3
        p0 = cls.REFERENCE_RSSI  # -40 dBm reference at 1m

        # Dynamic calibration if live RSSI and distance are available
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
            d_core = max(1.8, min(3.2, 10 ** ((p0 - cls.EXCELLENT) / (10 * n))))
            d_strong = max(5.0, min(9.0, 10 ** ((p0 - cls.GOOD) / (10 * n))))
            d_good = max(11.0, min(16.5, 10 ** ((p0 - cls.FAIR) / (10 * n))))
            d_fair = max(18.0, min(25.0, 10 ** ((p0 - cls.WEAK) / (10 * n))))
            d_max = max(26.0, min(35.0, 10 ** ((p0 - (-85.0)) / (10 * n))))
        else:
            d_core = max(2.2, min(4.0, 10 ** ((p0 - cls.EXCELLENT) / (10 * n))))
            d_strong = max(7.0, min(12.0, 10 ** ((p0 - cls.GOOD) / (10 * n))))
            d_good = max(15.0, min(22.0, 10 ** ((p0 - cls.FAIR) / (10 * n))))
            d_fair = max(25.0, min(36.0, 10 ** ((p0 - cls.WEAK) / (10 * n))))
            d_max = max(38.0, min(50.0, 10 ** ((p0 - (-85.0)) / (10 * n))))

        # Estimated effective indoor area (accounting for walls & obstacles: ~0.65 area efficiency)
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

    # ==================================================
    # CONNECTION STATUS
    # ==================================================

    @classmethod
    def connection_status(cls, rssi):

        if rssi is None:
            return "UNKNOWN"

        rssi = float(rssi)

        if rssi >= cls.FAIR:
            return "ACTIVE"

        if rssi >= cls.WEAK:
            return "WEAK"

        return "UNRELIABLE"

    # ==================================================
    # COMPLETE METRICS
    # ==================================================

    @classmethod
    def calculate(
        cls,
        rssi,
        degree=0,
        centrality=0.0
    ):

        distance = (
            cls.estimate_distance(
                rssi
            )
        )

        return {

            "signal": (
                round(float(rssi), 1)
                if rssi is not None
                else None
            ),

            "quality": (
                cls.signal_quality(
                    rssi
                )
            ),

            "distance": distance,

            "range": (
                cls.estimate_range()
            ),

            "status": (
                cls.connection_status(
                    rssi
                )
            ),

            "degree": degree,

            "centrality": round(
                float(centrality),
                3
            )
        }


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    print("=" * 60)
    print("       WAVEIUM DEVICE METRICS TEST")
    print("=" * 60)

    test_values = [
        -45,
        -55,
        -65,
        -75,
        -85
    ]

    for rssi in test_values:

        metrics = (
            DeviceMetrics.calculate(
                rssi
            )
        )

        print()
        print(
            f"RSSI       : "
            f"{metrics['signal']} dBm"
        )

        print(
            f"Quality    : "
            f"{metrics['quality']}"
        )

        print(
            f"Distance   : "
            f"~{metrics['distance']} m"
        )

        print(
            f"Range      : "
            f"~{metrics['range']} m"
        )

        print(
            f"Status     : "
            f"{metrics['status']}"
        )