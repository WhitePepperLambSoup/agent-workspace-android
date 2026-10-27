"""Announce the phone-connection endpoint on the local network (mDNS / DNS-SD).

Phones look for ``_agentworkspace._tcp`` to list nearby computers. The service is registered
with Windows' own mDNS responder (``DnsServiceRegister``, Windows 10 1809 and later), so this
process opens no socket of its own. The TXT record carries ``v=1``, the desktop id, whether the
endpoint is HTTPS (``tls``), the certificate fingerprint when it is, and ``pair=1`` while a
pairing code is shown. Elsewhere, or when the system refuses, nothing is announced and the
runtime document does not list the ``mdns`` feature.
"""

from __future__ import annotations

import ctypes
import os
import socket
import struct
import threading
from collections.abc import Callable
from ctypes import wintypes
from typing import Any

SERVICE_TYPE = "_agentworkspace._tcp"
_DNS_REQUEST_PENDING = 9506
_REGISTER_TIMEOUT_SECONDS = 5.0
_LINGERING: list[tuple[object, ...]] = []


def txt_record(
    *, desktop_id: str, tls: bool, fingerprint: str | None, pairing: bool
) -> dict[str, str]:
    record = {"v": "1", "id": desktop_id, "tls": "1" if tls else "0"}
    if tls and fingerprint:
        record["fp"] = fingerprint.lower()
    if pairing:
        record["pair"] = "1"
    return record


def instance_label(name: str) -> str:
    """The computer's name as one DNS label: no dots, at most 63 bytes."""
    label = " ".join(name.replace(".", " ").split()) or "Agent Workspace"
    while len(label.encode("utf-8")) > 63:
        label = label[:-1]
    return label


class _Instance(ctypes.Structure):
    _fields_ = [
        ("pszInstanceName", wintypes.LPWSTR),
        ("pszHostName", wintypes.LPWSTR),
        ("ip4Address", ctypes.POINTER(wintypes.DWORD)),
        ("ip6Address", ctypes.c_void_p),
        ("wPort", wintypes.WORD),
        ("wPriority", wintypes.WORD),
        ("wWeight", wintypes.WORD),
        ("dwPropertyCount", wintypes.DWORD),
        ("keys", ctypes.POINTER(wintypes.LPWSTR)),
        ("values", ctypes.POINTER(wintypes.LPWSTR)),
        ("dwInterfaceIndex", wintypes.DWORD),
    ]


_Completion = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(_Instance))


class _Request(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("InterfaceIndex", wintypes.ULONG),
        ("pServiceInstance", ctypes.POINTER(_Instance)),
        ("pRegisterCompletionCallback", _Completion),
        ("pQueryContext", ctypes.c_void_p),
        ("hCredentials", wintypes.HANDLE),
        ("unicastEnabled", wintypes.BOOL),
    ]


def _dnsapi() -> Any | None:
    if os.name != "nt":
        return None
    try:
        library = ctypes.WinDLL("dnsapi.dll")
        construct = library.DnsServiceConstructInstance
    except (OSError, AttributeError):
        return None
    construct.restype = ctypes.POINTER(_Instance)
    construct.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
        wintypes.WORD,
        wintypes.WORD,
        wintypes.WORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPCWSTR),
        ctypes.POINTER(wintypes.LPCWSTR),
    ]
    library.DnsServiceRegister.restype = wintypes.DWORD
    library.DnsServiceRegister.argtypes = [ctypes.POINTER(_Request), ctypes.c_void_p]
    library.DnsServiceDeRegister.restype = wintypes.DWORD
    library.DnsServiceDeRegister.argtypes = [ctypes.POINTER(_Request), ctypes.c_void_p]
    library.DnsServiceFreeInstance.restype = None
    library.DnsServiceFreeInstance.argtypes = [ctypes.POINTER(_Instance)]
    return library


class MdnsAnnouncer:
    """One registered service at a time; ``announce`` replaces it, ``stop`` withdraws it."""

    def __init__(self, *, library: Callable[[], Any | None] = _dnsapi) -> None:
        self._library_factory = library
        self._library: Any | None = None
        self._lock = threading.Lock()
        # The request, its callback and the instance, kept alive while the system holds them.
        self._registered: tuple[_Request, Any, Any] | None = None
        self._key: tuple[object, ...] | None = None

    @property
    def active(self) -> bool:
        return self._registered is not None

    def announce(
        self,
        *,
        name: str,
        port: int,
        address: str | None,
        txt: dict[str, str],
    ) -> bool:
        """Register (or re-register with a changed record); True when the system accepted it."""
        key = (name, port, address, tuple(sorted(txt.items())))
        with self._lock:
            if self._registered is not None and key == self._key:
                return True
            self._withdraw()
            if self._library is None:
                self._library = self._library_factory()
            library = self._library
            if library is None:
                return False
            host = f"{socket.gethostname()}.local"
            instance_name = f"{instance_label(name)}.{SERVICE_TYPE}.local"
            ip4 = None
            if address:
                try:
                    ip4 = ctypes.pointer(
                        wintypes.DWORD(struct.unpack("<I", socket.inet_aton(address))[0])
                    )
                except OSError:
                    ip4 = None
            keys = (wintypes.LPCWSTR * len(txt))(*txt.keys())
            values = (wintypes.LPCWSTR * len(txt))(*txt.values())
            instance = library.DnsServiceConstructInstance(
                instance_name, host, ip4, None, port, 0, 0, len(txt), keys, values
            )
            if not instance:
                return False
            done = threading.Event()
            outcome: list[int] = []

            def completed(status: int, _context: object, _instance: object) -> None:
                outcome.append(int(status))
                done.set()

            callback = _Completion(completed)
            request = _Request(1, 0, instance, callback, None, None, False)
            status = library.DnsServiceRegister(ctypes.byref(request), None)
            if status != _DNS_REQUEST_PENDING:
                library.DnsServiceFreeInstance(instance)
                return False
            done.wait(_REGISTER_TIMEOUT_SECONDS)
            if outcome and outcome[0] != 0:
                library.DnsServiceFreeInstance(instance)
                return False
            # The request, its callback and the instance stay alive until deregistration.
            self._registered = (request, callback, instance)
            self._key = key
            return True

    def stop(self) -> None:
        with self._lock:
            self._withdraw()

    def _withdraw(self) -> None:
        registered, self._registered, self._key = self._registered, None, None
        if registered is None or self._library is None:
            return
        request, _callback, instance = registered
        done = threading.Event()

        def completed(_status: int, _context: object, _instance: object) -> None:
            done.set()

        withdrawal = _Completion(completed)
        request.pRegisterCompletionCallback = withdrawal
        if self._library.DnsServiceDeRegister(ctypes.byref(request), None) == _DNS_REQUEST_PENDING:
            done.wait(_REGISTER_TIMEOUT_SECONDS)
        if done.is_set():
            self._library.DnsServiceFreeInstance(instance)
        else:
            # The system may still call back or read the instance: keep all of it alive.
            _LINGERING.append((request, withdrawal, instance))


__all__ = ["SERVICE_TYPE", "MdnsAnnouncer", "instance_label", "txt_record"]
