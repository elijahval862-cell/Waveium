import re
import socket
import subprocess
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed


class NetworkScanner:
    """
    Waveium Network Scanner

    Discovers:
    - Local IP
    - Default gateway
    - Wi-Fi information
    - ARP devices
    - Active devices on the local subnet
    """

    def __init__(self):
        self.local_ip = self.get_local_ip()
        self.gateway = self.get_gateway()

    # ============================================================
    # LOCAL IP
    # ============================================================

    def get_local_ip(self):
        """
        Determine the local IPv4 address.
        """

        try:
            sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            sock.connect(("8.8.8.8", 80))

            local_ip = sock.getsockname()[0]

            sock.close()

            return local_ip

        except Exception:
            try:
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)

            except Exception:
                return "127.0.0.1"

    # ============================================================
    # SUBNET INFORMATION
    # ============================================================

    def get_subnet_mask(self):
        """
        Detect the subnet mask for the active local IPv4 adapter.

        This is important because Waveium must not assume every
        network is /24. For example, 255.255.248.0 is /21 and
        contains 2046 usable host addresses.
        """

        try:
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5
            )

            lines = result.stdout.splitlines()

            # First look in the block containing our local IP.
            local_index = None
            for index, line in enumerate(lines):
                if self.local_ip and self.local_ip in line:
                    local_index = index
                    break

            if local_index is not None:
                for line in lines[local_index:local_index + 4]:
                    match = re.search(
                        r"Subnet Mask[^:]*:\s*(\d{1,3}(?:\.\d{1,3}){3})",
                        line,
                        re.IGNORECASE
                    )
                    if match:
                        return match.group(1)

            # Fallback: find any valid subnet mask near the Wi-Fi
            # adapter section.
            for index, line in enumerate(lines):
                if "Wireless LAN adapter Wi-Fi" in line:
                    for next_line in lines[index:index + 12]:
                        match = re.search(
                            r"Subnet Mask[^:]*:\s*(\d{1,3}(?:\.\d{1,3}){3})",
                            next_line,
                            re.IGNORECASE
                        )
                        if match:
                            return match.group(1)

        except Exception:
            pass

        return "255.255.255.0"

    def get_network(self):
        """Return the actual IPv4 network containing the local device."""
        try:
            mask = self.get_subnet_mask()
            return ipaddress.ip_network(
                f"{self.local_ip}/{mask}",
                strict=False
            )
        except Exception:
            try:
                return ipaddress.ip_network(
                    f"{self.local_ip}/24",
                    strict=False
                )
            except Exception:
                return None

    # ============================================================
    # DEFAULT GATEWAY
    # ============================================================

    def get_gateway(self):
        """
        Detect the Windows default gateway.

        Uses ipconfig and extracts the IPv4 address
        associated with Default Gateway.
        """

        try:
            result = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5
            )

            lines = result.stdout.splitlines()

            gateway_candidates = []

            for line in lines:

                if "Default Gateway" in line:

                    # Handle:
                    # Default Gateway . . . . . . : 192.168.1.1
                    match = re.search(
                        r"(\d{1,3}(?:\.\d{1,3}){3})",
                        line
                    )

                    if match:
                        gateway_candidates.append(
                            match.group(1)
                        )

            # Sometimes Windows prints the gateway
            # on the following line.
            if not gateway_candidates:

                for index, line in enumerate(lines):

                    if "Default Gateway" in line:

                        for next_line in lines[index + 1:index + 3]:

                            match = re.search(
                                r"(\d{1,3}(?:\.\d{1,3}){3})",
                                next_line
                            )

                            if match:
                                gateway_candidates.append(
                                    match.group(1)
                                )

            if gateway_candidates:
                return gateway_candidates[0]

        except Exception:
            pass

        # Fallback: assume the first three octets of
        # the local IP and .1 as gateway.
        try:
            parts = self.local_ip.split(".")

            if len(parts) == 4:
                return ".".join(parts[:3]) + ".1"

        except Exception:
            pass

        return "Unknown"

    # ============================================================
    # PING DEVICE
    # ============================================================

    def device_exists(self, ip):
        """
        Check whether a device responds to ping.
        """

        try:

            result = subprocess.run(
                [
                    "ping",
                    "-n",
                    "1",
                    "-w",
                    "350",
                    ip
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )

            return result.returncode == 0

        except Exception:
            return False

    # ============================================================
    # ACTIVE DEVICE SCAN
    # ============================================================

    def scan_devices(self):
        """
        Scan the actual local IPv4 subnet using the detected subnet mask.

        Unlike the old implementation, this does NOT assume /24.
        A network such as 172.21.56.0/21 is therefore scanned as
        172.21.56.1 through 172.21.63.254.
        """

        devices = []

        try:
            network = self.get_network()
            if network is None:
                return devices

            # ipaddress.hosts() automatically excludes network and
            # broadcast addresses.
            ip_addresses = [
                str(ip)
                for ip in network.hosts()
                if str(ip) != self.local_ip
            ]

            print(
                f"Subnet detected: {network} | "
                f"Hosts to scan: {len(ip_addresses)}"
            )

            def check_device(ip):
                if self.device_exists(ip):
                    return {
                        "ip": ip,
                        "mac": None,
                        "signal": None,
                        "rssi": None,
                        "rssi_type": "NOT MEASURED",
                        "status": "ACTIVE"
                    }
                return None

            # A larger worker pool keeps larger subnets practical
            # while each ping has a short timeout.
            worker_count = min(64, max(16, len(ip_addresses)))

            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(check_device, ip): ip
                    for ip in ip_addresses
                }

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            devices.append(result)
                    except Exception:
                        pass

            devices.sort(
                key=lambda item: tuple(
                    int(x) for x in item["ip"].split(".")
                )
            )

        except Exception as error:
            print("Subnet scan error:", error)

        return devices

    # ============================================================
    # DEVICE LATENCY
    # ============================================================

    def get_device_latency(self, ip):
        """
        Measure real latency to a discovered device.
        Returns milliseconds or None if unavailable.
        """

        try:
            result = subprocess.run(
                [
                    "ping",
                    "-n",
                    "1",
                    "-w",
                    "1000",
                    ip
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=2
            )

            output = result.stdout

            match = re.search(
                r"time[=<]\s*(\d+)\s*ms",
                output,
                re.IGNORECASE
            )

            if match:
                return float(match.group(1))

            if re.search(
                r"time<1ms",
                output,
                re.IGNORECASE
            ):
                return 0.5

        except Exception:
            pass

        return None

    # ============================================================
    # WI-FI INFORMATION
    # ============================================================

    def get_wifi_information(self):
        """
        Read the current Wi-Fi connection using:

            netsh wlan show interfaces

        Returns:
            SSID
            BSSID
            Signal %
            Estimated RSSI
            Band
            Channel
            Receive rate
            Transmit rate
        """

        wifi = {
            "ssid": None,
            "bssid": None,
            "signal_percent": None,
            "rssi": None,
            "band": None,
            "channel": None,
            "receive_rate": None,
            "transmit_rate": None
        }

        try:

            result = subprocess.run(
                [
                    "netsh",
                    "wlan",
                    "show",
                    "interfaces"
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5
            )

            output = result.stdout

            # ----------------------------------------------------
            # SSID
            # ----------------------------------------------------

            match = re.search(
                r"^\s*SSID\s*:\s*(.+)$",
                output,
                re.MULTILINE
            )

            if match:
                wifi["ssid"] = match.group(1).strip()

            # ----------------------------------------------------
            # BSSID
            # ----------------------------------------------------

            match = re.search(
                r"^\s*BSSID\s*:\s*(.+)$",
                output,
                re.MULTILINE
            )

            if match:
                wifi["bssid"] = match.group(1).strip()

            # ----------------------------------------------------
            # SIGNAL
            # ----------------------------------------------------

            match = re.search(
                r"^\s*Signal\s*:\s*(\d+)\s*%",
                output,
                re.MULTILINE
            )

            if match:

                signal = int(
                    match.group(1)
                )

                wifi["signal_percent"] = signal

                # Windows reports signal as percentage.
                # This is only an ESTIMATE of RSSI.
                estimated_rssi = (
                    (signal / 2) - 100
                )

                wifi["rssi"] = round(
                    estimated_rssi
                )

            # ----------------------------------------------------
            # CHANNEL
            # ----------------------------------------------------

            match = re.search(
                r"^\s*Channel\s*:\s*(\d+)",
                output,
                re.MULTILINE
            )

            if match:

                channel = int(
                    match.group(1)
                )

                wifi["channel"] = channel

                # Basic band classification.
                if channel <= 14:
                    wifi["band"] = "2.4 GHz"

                elif channel <= 177:
                    wifi["band"] = "5 GHz"

                else:
                    wifi["band"] = "6 GHz"

            # ----------------------------------------------------
            # RECEIVE RATE
            # ----------------------------------------------------

            match = re.search(
                r"^\s*Receive rate \(Mbps\)\s*:\s*([\d.]+)",
                output,
                re.MULTILINE
            )

            if match:

                wifi["receive_rate"] = float(
                    match.group(1)
                )

            # ----------------------------------------------------
            # TRANSMIT RATE
            # ----------------------------------------------------

            match = re.search(
                r"^\s*Transmit rate \(Mbps\)\s*:\s*([\d.]+)",
                output,
                re.MULTILINE
            )

            if match:

                wifi["transmit_rate"] = float(
                    match.group(1)
                )

        except Exception:
            pass

        return wifi

    # ============================================================
    # ARP TABLE
    # ============================================================

    def get_arp_devices(self):
        """
        Read the Windows ARP table.

        Multicast and broadcast addresses are excluded.
        """

        devices = []

        try:

            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=5
            )

            output = result.stdout

            for line in output.splitlines():

                match = re.search(
                    r"(\d{1,3}(?:\.\d{1,3}){3})\s+"
                    r"([0-9a-fA-F-]{17})\s+"
                    r"(\w+)",
                    line
                )

                if not match:
                    continue

                ip = match.group(1)
                mac = match.group(2)
                entry_type = match.group(3).lower()

                # ------------------------------------------------
                # Remove multicast addresses
                # 224.0.0.0 - 239.255.255.255
                # ------------------------------------------------

                first_octet = int(
                    ip.split(".")[0]
                )

                if 224 <= first_octet <= 239:
                    continue

                # ------------------------------------------------
                # Remove multicast / broadcast / invalid entries.
                # Use the actual detected network instead of assuming /24.
                # ------------------------------------------------

                try:
                    address = ipaddress.ip_address(ip)
                    network = self.get_network()

                    if address.is_multicast or address.is_unspecified:
                        continue

                    if ip == "255.255.255.255":
                        continue

                    if network is not None and (
                        address == network.network_address
                        or address == network.broadcast_address
                    ):
                        continue

                except Exception:
                    continue

                # ------------------------------------------------
                # Only dynamic/static ARP entries
                # ------------------------------------------------

                devices.append({
                    "ip": ip,
                    "mac": mac,
                    "type": entry_type
                })

        except Exception:
            pass

        return devices

    # ============================================================
    # COMBINED SCAN
    # ============================================================

    def scan(self):
        """
        Perform a complete Waveium network scan.

        Returns a dictionary compatible with
        WaveiumGraphGenerator.build_network().
        """

        print()
        print("Scanning Wi-Fi information...")

        wifi = self.get_wifi_information()

        print("Scanning ARP table...")

        arp_devices = self.get_arp_devices()

        print("Scanning connected devices...")

        ping_devices = self.scan_devices()

        # ========================================================
        # MERGE DEVICES
        # ========================================================

        device_map = {}

        # --------------------------------------------------------
        # Add ARP devices first because they contain MAC addresses.
        # --------------------------------------------------------

        for device in arp_devices:

            ip = device["ip"]

            device_map[ip] = {
                "ip": ip,
                "mac": device["mac"],
                "signal": None,
                "rssi": None,
                "rssi_type": "NOT MEASURED",
                "status": "ARP DISCOVERED"
            }

        # --------------------------------------------------------
        # Merge ping results.
        # --------------------------------------------------------

        for device in ping_devices:

            ip = device["ip"]

            if ip in device_map:

                device_map[ip]["status"] = "ACTIVE"

            else:

                device_map[ip] = device

        # --------------------------------------------------------
        # Remove local IP from device list.
        # --------------------------------------------------------

        if self.local_ip in device_map:
            del device_map[self.local_ip]

        # --------------------------------------------------------
        # Sort devices numerically by IP.
        # --------------------------------------------------------

        devices = list(
            device_map.values()
        )

        devices.sort(
            key=lambda item: tuple(
                int(x)
                for x in item["ip"].split(".")
            )
        )

        # ========================================================
        # MEASURE LATENCY FOR ALL DISCOVERED DEVICES
        # ========================================================

        def measure_device(device):
            latency = self.get_device_latency(
                device["ip"]
            )

            if latency is not None:
                device["latency_ms"] = latency

                if latency < 10:
                    device["latency_quality"] = "EXCELLENT"
                elif latency < 30:
                    device["latency_quality"] = "GOOD"
                elif latency < 60:
                    device["latency_quality"] = "FAIR"
                elif latency < 100:
                    device["latency_quality"] = "WEAK"
                else:
                    device["latency_quality"] = "POOR"
            else:
                device["latency_ms"] = None
                device["latency_quality"] = "NOT MEASURED"

            return device

        with ThreadPoolExecutor(
            max_workers=32
        ) as executor:

            futures = [
                executor.submit(
                    measure_device,
                    device
                )
                for device in devices
            ]

            devices = []

            for future in as_completed(futures):
                try:
                    devices.append(
                        future.result()
                    )
                except Exception:
                    pass

        devices.sort(
            key=lambda item: tuple(
                int(x)
                for x in item["ip"].split(".")
            )
        )

        # ========================================================
        # LATENCY SUMMARY
        # ========================================================

        measured_latencies = [
            device["latency_ms"]
            for device in devices
            if device.get("latency_ms") is not None
        ]

        if measured_latencies:
            latency_summary = {
                "measured_devices": len(measured_latencies),
                "average_latency_ms": round(
                    sum(measured_latencies)
                    / len(measured_latencies),
                    2
                ),
                "min_latency_ms": min(
                    measured_latencies
                ),
                "max_latency_ms": max(
                    measured_latencies
                )
            }
        else:
            latency_summary = {
                "measured_devices": 0,
                "average_latency_ms": None,
                "min_latency_ms": None,
                "max_latency_ms": None
            }

        # ========================================================
        # RESULT
        # ========================================================

        network = self.get_network()

        network_data = {
            "gateway": self.gateway,
            "local_ip": self.local_ip,
            "subnet_mask": self.get_subnet_mask(),
            "network_cidr": str(network) if network else None,
            "devices": devices,
            "wifi": wifi,
            "router_station_count": len(devices),
            "latency_summary": latency_summary
        }

        print(
            f"Scan complete: {len(devices)} devices found."
        )

        return network_data


# ================================================================
# DIRECT TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 60)
    print("        WAVEIUM NETWORK SCANNER TEST")
    print("=" * 60)

    scanner = NetworkScanner()

    print()
    print("Local IP :", scanner.local_ip)
    print("Gateway  :", scanner.gateway)

    data = scanner.scan()

    print()
    print("SCAN COMPLETE")
    print()

    print("Wi-Fi:")
    print(data["wifi"])

    print()
    print("Devices:")

    for device in data["devices"]:
        print(device)