import re
import subprocess


class NetworkAdapter:

    def __init__(
        self,
        interface_name="Wi-Fi"
    ):

        self.interface_name = (
            interface_name
        )

    # ======================================================
    # RUN WINDOWS COMMAND
    # ======================================================

    @staticmethod
    def run_command(
        command,
        timeout=10
    ):

        try:

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=timeout
            )

            return result.stdout

        except Exception:

            return ""

    # ======================================================
    # NORMALIZE MAC
    # ======================================================

    @staticmethod
    def normalize_mac(
        mac
    ):

        if not mac:

            return None

        cleaned = re.sub(
            r"[^0-9a-fA-F]",
            "",
            str(mac)
        ).lower()

        if len(cleaned) != 12:

            return None

        return ":".join(
            cleaned[i:i + 2]
            for i in range(
                0,
                12,
                2
            )
        )

    # ======================================================
    # SIGNAL → RSSI
    # ======================================================

    @staticmethod
    def signal_to_rssi(
        signal_percent
    ):

        if signal_percent is None:

            return None

        try:

            percent = int(
                signal_percent
            )

        except (
            ValueError,
            TypeError
        ):

            return None

        percent = max(
            0,
            min(
                100,
                percent
            )
        )

        # --------------------------------------------------
        # Windows reports Wi-Fi signal as a percentage.
        #
        # Waveium uses the same estimation as
        # NetworkScanner:
        #
        # RSSI ≈ (Signal % / 2) - 100
        #
        # Examples:
        # 100% → -50 dBm
        #  80% → -60 dBm
        #  60% → -70 dBm
        #  40% → -80 dBm
        #  20% → -90 dBm
        # --------------------------------------------------

        return int(
            round(
                (percent / 2)
                - 100
            )
        )

    # ======================================================
    # GET BSSID FROM WIFI SCAN
    # ======================================================

    def get_current_bssid(
        self,
        current_ssid
    ):

        if not current_ssid:

            return None

        output = self.run_command(
            [
                "netsh",
                "wlan",
                "show",
                "networks",
                "mode=bssid"
            ]
        )

        if not output:

            return None

        # --------------------------------------------------
        # Split into SSID blocks
        # --------------------------------------------------

        blocks = re.split(
            r"(?=^\s*SSID\s+\d+\s*:)",
            output,
            flags=re.MULTILINE
        )

        for block in blocks:

            ssid_match = re.search(
                r"^\s*SSID\s+\d+\s*:\s*(.*)$",
                block,
                re.MULTILINE
            )

            if not ssid_match:

                continue

            ssid = (
                ssid_match.group(1)
                .strip()
            )

            if ssid != current_ssid:

                continue

            # --------------------------------------------------
            # Find BSSID
            # --------------------------------------------------

            bssid_match = re.search(
                r"BSSID\s+\d+\s*:\s*"
                r"([0-9a-fA-F:-]+)",
                block,
                re.IGNORECASE
            )

            if bssid_match:

                return self.normalize_mac(
                    bssid_match.group(1)
                )

        return None

    # ======================================================
    # GET CURRENT AP DETAILS
    # ======================================================

    def get_current_ap_details(
        self,
        current_ssid
    ):

        output = self.run_command(
            [
                "netsh",
                "wlan",
                "show",
                "networks",
                "mode=bssid"
            ]
        )

        if not output:

            return {}

        blocks = re.split(
            r"(?=^\s*SSID\s+\d+\s*:)",
            output,
            flags=re.MULTILINE
        )

        for block in blocks:

            ssid_match = re.search(
                r"^\s*SSID\s+\d+\s*:\s*(.*)$",
                block,
                re.MULTILINE
            )

            if not ssid_match:

                continue

            ssid = (
                ssid_match.group(1)
                .strip()
            )

            if ssid != current_ssid:

                continue

            # --------------------------------------------------
            # First BSSID
            # --------------------------------------------------

            bssid_match = re.search(
                r"BSSID\s+\d+\s*:\s*"
                r"([0-9a-fA-F:-]+)",
                block,
                re.IGNORECASE
            )

            # --------------------------------------------------
            # Signal
            # --------------------------------------------------

            signal_match = re.search(
                r"Signal\s*:\s*(\d+)\s*%",
                block,
                re.IGNORECASE
            )

            # --------------------------------------------------
            # Band
            # --------------------------------------------------

            band_match = re.search(
                r"Band\s*:\s*(.+)",
                block,
                re.IGNORECASE
            )

            # --------------------------------------------------
            # Channel
            # --------------------------------------------------

            channel_match = re.search(
                r"Channel\s*:\s*(\d+)",
                block,
                re.IGNORECASE
            )

            details = {}

            if bssid_match:

                details[
                    "bssid"
                ] = self.normalize_mac(
                    bssid_match.group(1)
                )

            else:

                details[
                    "bssid"
                ] = None

            if signal_match:

                details[
                    "signal_percent"
                ] = int(
                    signal_match.group(1)
                )

            else:

                details[
                    "signal_percent"
                ] = None

            if band_match:

                details[
                    "band"
                ] = (
                    band_match.group(1)
                    .strip()
                )

            else:

                details[
                    "band"
                ] = None

            if channel_match:

                details[
                    "channel"
                ] = int(
                    channel_match.group(1)
                )

            else:

                details[
                    "channel"
                ] = None

            return details

        return {}

    # ======================================================
    # LIVE WI-FI INFORMATION
    # ======================================================

    def get_live_network(
        self
    ):

        output = self.run_command(
            [
                "netsh",
                "wlan",
                "show",
                "interfaces"
            ]
        )

        if not output:

            return {
                "error":
                    "Unable to read Wi-Fi interface."
            }

        # ==================================================
        # VALUE HELPER
        # ==================================================

        def get_value(
            label
        ):

            match = re.search(
                rf"^\s*{re.escape(label)}\s*:\s*(.*)$",
                output,
                re.MULTILINE
            )

            if match:

                return (
                    match.group(1)
                    .strip()
                )

            return None

        # ==================================================
        # BASIC INFORMATION
        # ==================================================

        name = (
            get_value("Name")
            or self.interface_name
        )

        state = (
            get_value("State")
            or "Unknown"
        )

        ssid = get_value(
            "SSID"
        )

        bssid = get_value(
            "BSSID"
        )

        signal_text = get_value(
            "Signal"
        )

        radio_type = get_value(
            "Radio type"
        )

        band = get_value(
            "Band"
        )

        channel_text = get_value(
            "Channel"
        )

        receive_text = get_value(
            "Receive rate (Mbps)"
        )

        transmit_text = get_value(
            "Transmit rate (Mbps)"
        )

        authentication = get_value(
            "Authentication"
        )

        cipher = get_value(
            "Cipher"
        )

        profile = get_value(
            "Profile"
        )

        # ==================================================
        # SIGNAL
        # ==================================================

        signal_percent = None

        if signal_text:

            match = re.search(
                r"(\d+)",
                signal_text
            )

            if match:

                signal_percent = int(
                    match.group(1)
                )

        # --------------------------------------------------
        # IMPORTANT:
        # Use the same RSSI conversion as NetworkScanner.
        # --------------------------------------------------

        rssi = (
            self.signal_to_rssi(
                signal_percent
            )
        )

        # ==================================================
        # SCAN FOR REAL BSSID
        # ==================================================

        scan_details = (
            self.get_current_ap_details(
                ssid
            )
        )

        # Prefer interface BSSID if available.

        normalized_interface_bssid = (
            self.normalize_mac(
                bssid
            )
        )

        if normalized_interface_bssid:

            final_bssid = (
                normalized_interface_bssid
            )

        else:

            final_bssid = (
                scan_details.get(
                    "bssid"
                )
            )

        # ==================================================
        # SCAN DETAILS FALLBACK
        # ==================================================

        if band is None:

            band = scan_details.get(
                "band"
            )

        if channel_text is None:

            channel = scan_details.get(
                "channel"
            )

        else:

            channel_match = re.search(
                r"(\d+)",
                channel_text
            )

            if channel_match:

                channel = int(
                    channel_match.group(1)
                )

            else:

                channel = (
                    scan_details.get(
                        "channel"
                    )
                )

        # ==================================================
        # RECEIVE RATE
        # ==================================================

        receive_rate = None

        if receive_text:

            match = re.search(
                r"(\d+(?:\.\d+)?)",
                receive_text
            )

            if match:

                receive_rate = float(
                    match.group(1)
                )

        # ==================================================
        # TRANSMIT RATE
        # ==================================================

        transmit_rate = None

        if transmit_text:

            match = re.search(
                r"(\d+(?:\.\d+)?)",
                transmit_text
            )

            if match:

                transmit_rate = float(
                    match.group(1)
                )

        # ==================================================
        # CONNECTED
        # ==================================================

        connected = (
            state.lower()
            == "connected"
        )

        # ==================================================
        # FINAL DATA
        # ==================================================

        return {

            "interface":
                name,

            "state":
                state,

            "connected":
                connected,

            "ssid":
                ssid,

            "bssid":
                final_bssid,

            "signal_percent":
                signal_percent,

            "rssi":
                rssi,

            "band":
                band,

            "channel":
                channel,

            "radio_type":
                radio_type,

            "receive_rate":
                receive_rate,

            "transmit_rate":
                transmit_rate,

            "authentication":
                authentication,

            "cipher":
                cipher,

            "profile":
                profile
        }

    # ======================================================
    # NEIGHBOR WI-FI SPECTRUM & CHANNEL SCAN
    # ======================================================

    def get_channel_scan(self):
        """
        Scans neighborhood Wi-Fi networks and BSSIDs, extracting:
        - SSID, BSSID, Signal %, RSSI, Channel, Band, Radio
        - Aggregated channel congestion on 2.4 GHz and 5 GHz
        - Cleanest recommended channels for 2.4 GHz and 5 GHz
        """
        out = self.run_command(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=6)
        networks = []
        cur_ssid = None
        cur_auth = None
        cur_enc = None

        lines = out.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_ssid = re.search(r'^\s*SSID\s+\d+\s*:\s*(.*)$', line)
            if m_ssid:
                cur_ssid = m_ssid.group(1).strip()
                i += 1
                continue
            m_auth = re.search(r'^\s*Authentication\s*:\s*(.*)$', line)
            if m_auth:
                cur_auth = m_auth.group(1).strip()
            m_enc = re.search(r'^\s*Encryption\s*:\s*(.*)$', line)
            if m_enc:
                cur_enc = m_enc.group(1).strip()

            m_bssid = re.search(r'^\s*BSSID\s+\d+\s*:\s*([0-9a-fA-F:]{17})', line)
            if m_bssid:
                bssid = m_bssid.group(1).lower()
                sig = None
                chan = None
                band = "2.4 GHz"
                radio = "802.11n"
                j = i + 1
                while j < len(lines) and not re.search(r'^\s*(BSSID|SSID)\s+\d+', lines[j]):
                    l2 = lines[j]
                    m_s = re.search(r'^\s*Signal\s*:\s*(\d+)%', l2)
                    if m_s:
                        sig = int(m_s.group(1))
                    m_c = re.search(r'^\s*Channel\s*:\s*(\d+)', l2)
                    if m_c:
                        chan = int(m_c.group(1))
                    m_b = re.search(r'^\s*Band\s*:\s*(.+)$', l2)
                    if m_b:
                        band = m_b.group(1).strip()
                    m_r = re.search(r'^\s*Radio type\s*:\s*(.+)$', l2)
                    if m_r:
                        radio = m_r.group(1).strip()
                    j += 1
                i = j - 1
                if chan is not None:
                    if not band or ("2.4" not in band and "5" not in band):
                        band = "5 GHz" if chan >= 36 else "2.4 GHz"
                    networks.append({
                        "ssid": cur_ssid if cur_ssid else "Hidden Network",
                        "bssid": bssid,
                        "signal": sig,
                        "rssi": round((sig / 2) - 100) if sig is not None else None,
                        "channel": chan,
                        "band": band,
                        "radio": radio,
                        "authentication": cur_auth or "WPA2",
                        "encryption": cur_enc or "CCMP"
                    })
            i += 1

        # Current live connection
        live = self.get_live_network()
        current_ssid = live.get("ssid")
        current_chan = live.get("channel")
        current_band = live.get("band", "5 GHz")

        # Congestion counts
        channels_2g = {ch: 0 for ch in range(1, 14)}
        channels_5g = {ch: 0 for ch in [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]}

        for net in networks:
            ch = net.get("channel")
            if ch in channels_2g:
                channels_2g[ch] += 1
            elif ch in channels_5g:
                channels_5g[ch] += 1

        # Best channel recommendations
        best_2g = min([1, 6, 11], key=lambda c: channels_2g.get(c, 0))
        cand_5g = [36, 40, 44, 48, 149, 153, 157, 161]
        best_5g = min(cand_5g, key=lambda c: channels_5g.get(c, 0))

        return {
            "current_ssid": current_ssid,
            "current_channel": current_chan,
            "current_band": current_band,
            "networks": networks,
            "channels_2g": channels_2g,
            "channels_5g": channels_5g,
            "best_2g_channel": best_2g,
            "best_5g_channel": best_5g,
            "total_visible_networks": len(networks)
        }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    adapter = NetworkAdapter()

    network = (
        adapter.get_live_network()
    )

    print()
    print(
        "=" * 55
    )

    print(
        "WAVEIUM LIVE WI-FI DATA"
    )

    print(
        "=" * 55
    )

    for key, value in network.items():

        print(
            f"{key:<20}: {value}"
        )