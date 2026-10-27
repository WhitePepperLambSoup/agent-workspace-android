"""This computer's network addresses a phone can reach.

Only adapters that are up and are real network cards (Ethernet or Wi-Fi) count, plus Tailscale.
Virtual adapters that only lead inside this computer (WSL, Hyper-V, VMware, VirtualBox, Docker),
VPN taps and Bluetooth are left out, so a phone is never handed an address it cannot reach.
Windows reports adapters through GetAdaptersAddresses; elsewhere the addresses come from the
host name and the default route.
"""

from __future__ import annotations

import ctypes
import ipaddress
import os
import re
import socket
from contextlib import suppress
from ctypes import wintypes
from dataclasses import dataclass

_TAILSCALE = ipaddress.ip_network("100.64.0.0/10")
_ETHERNET = 6
_WIRELESS = 71
_UP = 1
_VIRTUAL = re.compile(
    r"virtual|hyper-v|vmware|virtualbox|vbox|wsl|docker|tap-|\btap\b|\btun\b|wintun|wireguard|"
    r"vpn|loopback|bluetooth|npcap|zerotier|teredo|pseudo|kernel debug",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Adapter:
    name: str
    description: str
    if_type: int
    up: bool
    addresses: tuple[str, ...]

    @property
    def physical(self) -> bool:
        return (
            self.if_type in {_ETHERNET, _WIRELESS}
            and not _VIRTUAL.search(self.description)
            and not _VIRTUAL.search(self.name)
        )


class _SocketAddress(ctypes.Structure):
    _fields_ = [("lpSockaddr", ctypes.c_void_p), ("iSockaddrLength", ctypes.c_int)]


class _Unicast(ctypes.Structure):
    pass


_Unicast._fields_ = [
    ("Length", wintypes.ULONG),
    ("Flags", wintypes.DWORD),
    ("Next", ctypes.POINTER(_Unicast)),
    ("Address", _SocketAddress),
]


class _Adapter(ctypes.Structure):
    pass


_Adapter._fields_ = [
    ("Length", wintypes.ULONG),
    ("IfIndex", wintypes.DWORD),
    ("Next", ctypes.POINTER(_Adapter)),
    ("AdapterName", ctypes.c_char_p),
    ("FirstUnicastAddress", ctypes.POINTER(_Unicast)),
    ("FirstAnycastAddress", ctypes.c_void_p),
    ("FirstMulticastAddress", ctypes.c_void_p),
    ("FirstDnsServerAddress", ctypes.c_void_p),
    ("DnsSuffix", ctypes.c_wchar_p),
    ("Description", ctypes.c_wchar_p),
    ("FriendlyName", ctypes.c_wchar_p),
    ("PhysicalAddress", ctypes.c_ubyte * 8),
    ("PhysicalAddressLength", wintypes.ULONG),
    ("Flags", wintypes.ULONG),
    ("Mtu", wintypes.ULONG),
    ("IfType", wintypes.DWORD),
    ("OperStatus", ctypes.c_int),
]


def windows_adapters() -> list[Adapter] | None:
    """Every IPv4 adapter Windows knows, or None when they cannot be read."""
    if os.name != "nt":
        return None
    try:
        function = ctypes.WinDLL("iphlpapi.dll").GetAdaptersAddresses
    except (OSError, AttributeError):
        return None
    function.restype = wintypes.ULONG
    function.argtypes = [
        wintypes.ULONG,
        wintypes.ULONG,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.ULONG),
    ]
    # Skip anycast, multicast and DNS server lists: only unicast addresses are needed.
    flags = 0x2 | 0x4 | 0x8
    size = wintypes.ULONG(16 * 1024)
    for _ in range(4):
        buffer = ctypes.create_string_buffer(size.value)
        result = function(
            socket.AF_INET, flags, None, ctypes.cast(buffer, ctypes.c_void_p), ctypes.byref(size)
        )
        if result == 0:
            break
        if result != 111:  # ERROR_BUFFER_OVERFLOW: size now holds what is needed
            return None
    else:
        return None
    adapters: list[Adapter] = []
    node = ctypes.cast(buffer, ctypes.POINTER(_Adapter))
    while node:
        entry = node.contents
        addresses: list[str] = []
        unicast = entry.FirstUnicastAddress
        while unicast:
            sockaddr = unicast.contents.Address.lpSockaddr
            if sockaddr and unicast.contents.Address.iSockaddrLength >= 8:
                family = ctypes.cast(sockaddr, ctypes.POINTER(ctypes.c_ushort)).contents.value
                if family == socket.AF_INET:
                    raw = ctypes.string_at(sockaddr + 4, 4)
                    addresses.append(socket.inet_ntoa(raw))
            unicast = unicast.contents.Next
        adapters.append(
            Adapter(
                name=entry.FriendlyName or "",
                description=entry.Description or "",
                if_type=int(entry.IfType),
                up=entry.OperStatus == _UP,
                addresses=tuple(addresses),
            )
        )
        node = entry.Next
    return adapters


def default_route_address() -> str | None:
    """The address this computer uses to reach other networks; connecting a UDP socket sends
    nothing."""
    with suppress(OSError), socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("10.255.255.255", 1))
        return str(probe.getsockname()[0])
    return None


def _usable(address: str) -> str | None:
    """ "lan" or "tailscale" for an address a phone could use, else None."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if ip in _TAILSCALE:
        return "tailscale"
    if ip.is_private and not ip.is_loopback and not ip.is_link_local:
        return "lan"
    return None


def reachable_addresses(
    adapters: list[Adapter] | None = None, route: str | None = None
) -> list[tuple[str, str]]:
    """(address, kind) pairs, LAN first with the default route's address leading."""
    if adapters is None:
        adapters = windows_adapters()
    if route is None:
        route = default_route_address()
    found: dict[str, str] = {}
    if adapters is not None:
        for adapter in adapters:
            if not adapter.up:
                continue
            for address in adapter.addresses:
                kind = _usable(address)
                # Tailscale's own adapter is virtual, but its address is how a phone away from
                # home reaches this computer.
                if kind == "tailscale" or (kind == "lan" and adapter.physical):
                    found[address] = kind
    else:
        candidates: set[str] = set()
        with suppress(OSError):
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                candidates.add(str(info[4][0]))
        if route:
            candidates.add(route)
        for address in candidates:
            kind = _usable(address)
            if kind is not None:
                found[address] = kind
    return sorted(
        found.items(),
        key=lambda item: (item[1] != "lan", item[0] != route, ipaddress.ip_address(item[0])),
    )


__all__ = ["Adapter", "default_route_address", "reachable_addresses", "windows_adapters"]
