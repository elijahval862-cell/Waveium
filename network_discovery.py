import ipaddress
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed


class NetworkDiscovery:

    # ==================================================
    # GET DEFAULT GATEWAY
    # ==================================================

    @staticmethod
    def get_default_gateway():

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

            # Windows may print the gateway on the same
            # line or on the following line.
            for index, line in enumerate(lines):

                if "Default Gateway" not in line:
                    continue

                match = re.search(
                    r"(\d{1,3}(?:\.\d{1,3}){3})",
                    line
                )

                if match:
                    return match.group(1)

                for next_line in lines[index + 1:index + 3]:

                    match = re.search(
                        r"(\d{1,3}(?:\.\d{1,3}){3})",
                        next_line
                    )

                    if match:
                        return match.group(1)

        except Exception:
            pass

        return None

    # ==================================================
    # GET LOCAL IPv4 ADDRESS
    # ==================================================

    @staticmethod
    def get_local_ip():

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
            wifi_section = False

            for line in lines:

                if (
                    "Wireless LAN adapter Wi-Fi"
                    in line
                ):
                    wifi_section = True
                    continue

                if (
                    wifi_section
                    and "adapter" in line.lower()
                    and "Wi-Fi" not in line
                ):
                    wifi_section = False

                if (
                    wifi_section
                    and "IPv4 Address" in line
                ):

                    match = re.search(
                        r"(\d+\.\d+\.\d+\.\d+)",
                        line
                    )

                    if match:
                        return match.group(1)

        except Exception:
            pass

        return None

    # ==================================================
    # BUILD LOCAL SUBNET
    # ==================================================

    @staticmethod
    def get_local_network():

        local_ip = NetworkDiscovery.get_local_ip()

        if not local_ip:
            return None

        try:

            return ipaddress.ip_network(
                f"{local_ip}/24",
                strict=False
            )

        except ValueError:

            return None

    # ==================================================
    # PING ONE DEVICE + LATENCY
    # ==================================================

    @staticmethod
    def ping_device(ip):

        """
        Ping one device and return real response latency.

        Returns:
            {
                "ip": "...",
                "active": True/False,
                "latency_ms": number or None
            }
        """

        ip = str(ip)

        try:

            result = subprocess.run(
                [
                    "ping",
                    "-n",
                    "1",
                    "-w",
                    "500",
                    ip
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=1.5
            )

            if result.returncode != 0:

                return {
                    "ip": ip,
                    "active": False,
                    "latency_ms": None
                }

            output = result.stdout

            # Windows ping normally reports:
            #
            # Reply from 192.168.1.1: bytes=32
            # time<1ms TTL=64
            #
            # Also handle:
            # time=12ms

            match = re.search(
                r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms",
                output,
                re.IGNORECASE
            )

            if match:

                latency = float(
                    match.group(1)
                )

            else:

                # Windows can display "<1ms".
                if re.search(
                    r"time<\s*1\s*ms",
                    output,
                    re.IGNORECASE
                ):
                    latency = 0.5
                else:
                    latency = None

            return {
                "ip": ip,
                "active": True,
                "latency_ms": latency
            }

        except Exception:

            return {
                "ip": ip,
                "active": False,
                "latency_ms": None
            }

    # ==================================================
    # LATENCY QUALITY
    # ==================================================

    @staticmethod
    def latency_quality(latency_ms):

        if latency_ms is None:
            return "UNKNOWN"

        latency_ms = float(latency_ms)

        if latency_ms < 10:
            return "EXCELLENT"

        if latency_ms < 30:
            return "GOOD"

        if latency_ms < 60:
            return "FAIR"

        if latency_ms < 100:
            return "WEAK"

        return "POOR"

    # ==================================================
    # DISCOVER ACTIVE DEVICES
    # ==================================================

    def scan_local_network(self):

        network = self.get_local_network()

        if network is None:
            return []

        active_devices = []

        addresses = list(network.hosts())

        with ThreadPoolExecutor(
            max_workers=30
        ) as executor:

            futures = {
                executor.submit(
                    self.ping_device,
                    ip
                ): ip
                for ip in addresses
            }

            for future in as_completed(futures):

                try:

                    result = future.result()

                    if result.get("active"):

                        result["latency_quality"] = (
                            self.latency_quality(
                                result.get(
                                    "latency_ms"
                                )
                            )
                        )

                        active_devices.append(
                            result
                        )

                except Exception:
                    pass

        return sorted(
            active_devices,
            key=lambda device:
                ipaddress.ip_address(
                    device["ip"]
                )
        )

    # ==================================================
    # GET ARP INFORMATION
    # ==================================================

    @staticmethod
    def get_arp_devices():

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

            for line in result.stdout.splitlines():

                match = re.search(
                    r"(\d+\.\d+\.\d+\.\d+)\s+"
                    r"([0-9a-fA-F-]{17})\s+"
                    r"(\w+)",
                    line
                )

                if not match:
                    continue

                ip = match.group(1)

                if not NetworkDiscovery.is_real_device(ip):
                    continue

                devices.append(
                    {
                        "ip": ip,
                        "mac": match.group(2),
                        "type": match.group(3)
                    }
                )

        except Exception:
            pass

        return devices

    # ==================================================
    # CHECK REAL LOCAL DEVICE
    # ==================================================

    @staticmethod
    def is_real_device(ip):

        try:

            address = ipaddress.ip_address(ip)

            if address.is_multicast:
                return False

            if address.is_unspecified:
                return False

            if address.is_reserved:
                return False

            if ip == "255.255.255.255":
                return False

            return True

        except ValueError:

            return False

    # ==================================================
    # COMPLETE DISCOVERY
    # ==================================================

    def discover(self):

        gateway = self.get_default_gateway()
        local_ip = self.get_local_ip()
        network = self.get_local_network()

        print()
        print(f"Local IP       : {local_ip}")
        print(f"Local Network  : {network}")
        print(f"Gateway        : {gateway}")
        print()
        print("Scanning local network...")

        # --------------------------------------------------
        # IMPORTANT:
        # ARP is used for DEVICE DISCOVERY.
        # Ping is used only for LATENCY when available.
        #
        # A device does NOT need to answer ping in order
        # to remain in Waveium's discovered-device list.
        # --------------------------------------------------

        arp_devices = self.get_arp_devices()

        arp_lookup = {
            device["ip"]: device
            for device in arp_devices
        }

        # Get active ping results. These are supplementary.
        ping_results = self.scan_local_network()

        ping_lookup = {
            device["ip"]: device
            for device in ping_results
        }

        print(
            f"ARP devices found: "
            f"{len(arp_devices)}"
        )

        print(
            f"Ping responses: "
            f"{len(ping_results)}"
        )

        # --------------------------------------------------
        # Build discovered device list from ARP first.
        # --------------------------------------------------

        candidate_ips = set(arp_lookup.keys())

        # Also retain devices discovered by ping.
        candidate_ips.update(
            ping_lookup.keys()
        )

        devices = []

        for ip in sorted(
            candidate_ips,
            key=lambda address:
                ipaddress.ip_address(address)
        ):

            if not self.is_real_device(ip):
                continue

            # Gateway and local computer are represented
            # separately in Waveium.
            if ip == gateway or ip == local_ip:
                continue

            arp_data = arp_lookup.get(
                ip,
                {}
            )

            ping_data = ping_lookup.get(
                ip,
                {}
            )

            latency = ping_data.get(
                "latency_ms"
            )

            if ping_data.get("active"):

                status = "ACTIVE"

                quality = self.latency_quality(
                    latency
                )

            else:

                status = "DISCOVERED"

                quality = "NOT MEASURED"

            devices.append(
                {
                    "ip": ip,

                    "mac": arp_data.get(
                        "mac"
                    ),

                    "type": arp_data.get(
                        "type",
                        "active"
                    ),

                    "status": status,

                    "latency_ms": latency,

                    "latency_quality": quality,

                    # Remote Wi-Fi RSSI is not available
                    # from this Windows LAN scan, so do not
                    # invent an RSSI value.
                    "rssi": None,

                    "signal": None,

                    "rssi_type": "NOT MEASURED"
                }
            )

        # --------------------------------------------------
        # LATENCY SUMMARY
        # --------------------------------------------------

        latencies = [
            device["latency_ms"]
            for device in devices
            if device["latency_ms"] is not None
        ]

        if latencies:

            latency_summary = {
                "min_ms": round(
                    min(latencies),
                    2
                ),

                "max_ms": round(
                    max(latencies),
                    2
                ),

                "average_ms": round(
                    sum(latencies)
                    / len(latencies),
                    2
                ),

                "measured_devices": len(
                    latencies
                )
            }

        else:

            latency_summary = {
                "min_ms": None,
                "max_ms": None,
                "average_ms": None,
                "measured_devices": 0
            }

        return {
            "gateway": gateway,

            "local_ip": local_ip,

            "network": (
                str(network)
                if network
                else None
            ),

            "devices": devices,

            "latency_summary": latency_summary
        }


# ======================================================
# TEST
# ======================================================

if __name__ == "__main__":

    print("=" * 60)
    print("        WAVEIUM ACTIVE NETWORK DISCOVERY")
    print("=" * 60)

    discovery = NetworkDiscovery()

    network = discovery.discover()

    print()
    print("=" * 60)
    print("ACTIVE DEVICES")
    print("=" * 60)

    print()

    print(
        f"Router/Gateway : "
        f"{network['gateway']}"
    )

    print(
        f"Your Device    : "
        f"{network['local_ip']}"
    )

    print()

    for device in network["devices"]:

        latency = device.get(
            "latency_ms"
        )

        latency_text = (
            f"{latency:.2f} ms"
            if latency is not None
            else "N/A"
        )

        print(
            f"IP: {device['ip']:<16} "
            f"MAC: {str(device['mac']):<18} "
            f"Latency: {latency_text:<10} "
            f"Quality: {device['latency_quality']}"
        )

    print()

    summary = network[
        "latency_summary"
    ]

    print(
        f"Latency Average : "
        f"{summary['average_ms']} ms"
    )

    print(
        f"Latency Minimum : "
        f"{summary['min_ms']} ms"
    )

    print(
        f"Latency Maximum : "
        f"{summary['max_ms']} ms"
    )

    print(
        f"Devices measured: "
        f"{summary['measured_devices']}"
    )

    print()
    print(
        f"Devices found: "
        f"{len(network['devices'])}"
    )
