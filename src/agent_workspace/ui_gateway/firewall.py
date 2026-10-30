"""Whether Windows Firewall lets phones reach the phone connection, and the one-click fix.

The check reads the active firewall policy for the networks this computer is on (real network
cards only) and the rules for the program that listens (the sidecar). Phones are blocked when
the firewall is on for one of those networks and either a rule blocks the program there (the
user once closed Windows' prompt with Cancel) or incoming connections are blocked by default and
no rule allows the program.

The fix asks Windows for administrator rights (its own confirmation is the only thing the user
sees), removes the program's blocking rules and adds one allowing it, only from private
networks and Tailscale.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

RULE_NAME = "Agent Workspace phone connection"
_CHECK_SECONDS = 600.0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_REMOTE_ADDRESSES = (
    "LocalSubnet",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",
)

# Through the firewall's COM interface (a few seconds; the NetSecurity cmdlets take ~20). The
# program path comes in through an environment variable, so it needs no quoting. Profiles are
# bits: 1 domain, 2 private, 4 public; actions 0 block, 1 allow; direction 1 is inbound.
_CHECK = r"""
$ErrorActionPreference = 'SilentlyContinue'
$fw = New-Object -ComObject HNetCfg.FwPolicy2
$active = $fw.CurrentProfileTypes
$program = [Environment]::ExpandEnvironmentVariables($env:AW_PROGRAM)
$profiles = @(foreach ($bit in 1, 2, 4) {
  if ($active -band $bit) {
    [pscustomobject]@{ bit = $bit; enabled = [bool]$fw.FirewallEnabled($bit);
      inbound = [int]$fw.DefaultInboundAction($bit) }
  }
})
$rules = @(foreach ($rule in $fw.Rules) {
  if ($rule.Enabled -and $rule.Direction -eq 1 -and $rule.ApplicationName) {
    if ([Environment]::ExpandEnvironmentVariables($rule.ApplicationName) -ieq $program) {
      [pscustomobject]@{ action = [int]$rule.Action; profiles = [int]$rule.Profiles }
    }
  }
})
[pscustomobject]@{ profiles = $profiles; rules = $rules } | ConvertTo-Json -Compress -Depth 3
"""


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def fix_script(program: str) -> str:
    """What runs with administrator rights: the program's blocking rules go, one rule allows it."""
    remote = ",".join(_quote(item) for item in _REMOTE_ADDRESSES)
    return (
        "$ErrorActionPreference = 'Stop'\n"
        f"$program = {_quote(program)}\n"
        "Get-NetFirewallApplicationFilter -Program $program -ErrorAction SilentlyContinue | "
        "Get-NetFirewallRule | Where-Object { [string]$_.Direction -eq 'Inbound' -and "
        "[string]$_.Action -eq 'Block' } | Remove-NetFirewallRule\n"
        f"Get-NetFirewallRule -DisplayName {_quote(RULE_NAME)} -ErrorAction SilentlyContinue | "
        "Remove-NetFirewallRule\n"
        f"New-NetFirewallRule -DisplayName {_quote(RULE_NAME)} -Direction Inbound -Action Allow "
        f"-Program $program -Protocol TCP -Profile Any -RemoteAddress @({remote}) | Out-Null\n"
    )


def assess(document: dict[str, Any]) -> str:
    """ "open", "blocked" or "unknown" from what the check read: blocked when, on a network this
    computer is on, the firewall is on and either a rule blocks the program or nothing allows
    it while incoming connections are blocked by default."""
    profiles = [item for item in document.get("profiles") or [] if isinstance(item, dict)]
    if not profiles:
        return "unknown"  # no network connected
    rules = [item for item in document.get("rules") or [] if isinstance(item, dict)]
    for profile in profiles:
        bit = profile.get("bit")
        if not isinstance(bit, int) or profile.get("enabled") is False:
            continue
        covering = [
            rule
            for rule in rules
            if isinstance(rule.get("profiles"), int) and rule["profiles"] & bit
        ]
        if any(rule.get("action") == 0 for rule in covering):
            return "blocked"
        if profile.get("inbound") == 1 or any(rule.get("action") == 1 for rule in covering):
            continue
        return "blocked"
    return "open"


def _powershell(
    script: str, *, env: dict[str, str] | None = None, timeout: float
) -> subprocess.CompletedProcess[str]:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        # Not the gateway's stdin: a child given a pipe another thread is reading waits at
        # start until that read ends (Windows).
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        creationflags=_NO_WINDOW,
        check=False,
    )


def check(program: str) -> str:
    if os.name != "nt":
        return "unknown"
    try:
        completed = _powershell(_CHECK, env={**os.environ, "AW_PROGRAM": program}, timeout=60)
        document = json.loads(completed.stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return "unknown"
    return assess(document) if isinstance(document, dict) else "unknown"


def allow(program: str) -> bool:
    """Run the fix with administrator rights; False when the user declined or it failed."""
    if os.name != "nt":
        return False
    inner = base64.b64encode(fix_script(program).encode("utf-16-le")).decode("ascii")
    outer = (
        "$p = Start-Process -FilePath powershell.exe -Verb RunAs -WindowStyle Hidden -Wait "
        "-PassThru -ArgumentList '-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass',"
        f"'-EncodedCommand','{inner}'; exit $p.ExitCode"
    )
    try:
        completed = _powershell(outer, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


class FirewallWatch:
    """The firewall state for the listening program, checked off the request path.

    ``state`` answers at once from the last check ("checking" before the first one) and starts a
    new check when it is old. ``allow`` runs the fix on its own thread; the state is "fixing"
    until it ends, then "declined" or a fresh check result.
    """

    def __init__(
        self,
        program: str | None = None,
        *,
        checker: Callable[[str], str] = check,
        fixer: Callable[[str], bool] = allow,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.program = program or sys.executable
        self._checker = checker
        self._fixer = fixer
        self._clock = clock
        self._lock = threading.Lock()
        self._state = "checking"
        self._checked_at: float | None = None
        self._busy = False

    def state(self) -> str:
        with self._lock:
            stale = self._checked_at is None or self._clock() - self._checked_at > _CHECK_SECONDS
            if stale and not self._busy:
                self._start(self._check)
            return self._state

    def recheck(self) -> None:
        with self._lock:
            if not self._busy:
                self._start(self._check)

    def allow(self) -> str:
        with self._lock:
            if self._state != "fixing":
                self._state = "fixing"
                self._start(self._fix, force=True)
            return self._state

    def _start(self, work: Callable[[], None], *, force: bool = False) -> None:
        if self._busy and not force:
            return
        self._busy = True
        threading.Thread(target=work, name="device-link-firewall", daemon=True).start()

    def _check(self) -> None:
        result = self._checker(self.program)
        with self._lock:
            if self._state != "fixing":
                self._state = result
            self._checked_at = self._clock()
            self._busy = False

    def _fix(self) -> None:
        allowed = self._fixer(self.program)
        result = self._checker(self.program)
        with self._lock:
            self._state = result if allowed or result == "open" else "declined"
            self._checked_at = self._clock()
            self._busy = False


__all__ = ["RULE_NAME", "FirewallWatch", "allow", "assess", "check", "fix_script"]
