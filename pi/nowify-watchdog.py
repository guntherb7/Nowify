#!/usr/bin/env python3
"""
Nowify kiosk watchdog.

Reads Nowify's auth state out of the running Chromium kiosk via the DevTools
Protocol (no changes to the Nowify app required) and decides whether a restart
would actually help:

  - logged in / playing            -> healthy, do nothing
  - NOT logged in, refreshToken    -> transient (browser hung, network blip at
    still present                      boot, mid-refresh). A restart fixes this.
  - NOT logged in, NO refreshToken -> refresh token expired/revoked. A restart
                                      CANNOT fix this; it needs a human to click
                                      "Login with Spotify" once. Do nothing, so
                                      we never get into a reboot/restart loop.

Only restarts after FAIL_THRESHOLD consecutive bad checks, so a single check
landing mid-refresh doesn't cause a needless restart.

Requires: python3 + websocket-client  (sudo apt install python3-websocket
or: pip3 install websocket-client). Chromium must be launched with
  --remote-debugging-port=9222
"""

import json
import os
import subprocess
import sys
import urllib.request

# --- config (env overrides) --------------------------------------------------
DEBUG_PORT = int(os.environ.get("NOWIFY_DEBUG_PORT", "9222"))
# Substring used to pick the Nowify tab if several are open. Matched against the
# tab url+title, lowercased. Leave as "nowify" or set to your host/port.
APP_HINT = os.environ.get("NOWIFY_APP_HINT", "nowify").lower()
# Shell command that relaunches the Chromium kiosk. REQUIRED — set per setup.
# Examples:
#   systemd system service: "sudo systemctl restart nowify-kiosk"
#   systemd user service:   "systemctl --user restart nowify-kiosk"
#   X/autostart (no svc):   "pkill -f chromium; sleep 2; <full chromium cmd> &"
RESTART_CMD = os.environ.get("NOWIFY_RESTART_CMD", "")
# Consecutive bad checks before we act (with a 5-min timer that's ~15 min).
FAIL_THRESHOLD = int(os.environ.get("NOWIFY_FAIL_THRESHOLD", "3"))
STATE_FILE = os.environ.get("NOWIFY_STATE_FILE", "/tmp/nowify-watchdog.count")
# -----------------------------------------------------------------------------


def log(msg):
    print(f"[nowify-watchdog] {msg}", flush=True)


def read_count():
    try:
        return int(open(STATE_FILE).read().strip())
    except Exception:
        return 0


def write_count(n):
    try:
        open(STATE_FILE, "w").write(str(n))
    except Exception as e:
        log(f"could not write state file: {e}")


def cdp_page_ws():
    """Return the websocket debugger URL for the Nowify tab, or None."""
    data = json.load(urllib.request.urlopen(f"http://localhost:{DEBUG_PORT}/json", timeout=5))
    pages = [t for t in data if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
    if not pages:
        return None
    for t in pages:
        if APP_HINT in (t.get("url", "") + " " + t.get("title", "")).lower():
            return t["webSocketDebuggerUrl"]
    return pages[0]["webSocketDebuggerUrl"]


def cdp_eval(ws_url, expression):
    from websocket import create_connection  # imported late so missing dep is a clear error

    ws = create_connection(ws_url, timeout=5)
    try:
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True},
        }))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                return msg.get("result", {}).get("result", {}).get("value")
    finally:
        ws.close()


def get_state():
    """
    Returns one of: 'healthy', 'transient', 'expired', 'unreachable'.
    """
    try:
        ws = cdp_page_ws()
    except Exception as e:
        log(f"Chromium DevTools not reachable on :{DEBUG_PORT} ({e}) -> unreachable")
        return "unreachable"

    if not ws:
        log("No Chromium page target found -> unreachable")
        return "unreachable"

    expr = (
        "JSON.stringify((function(){"
        "try{var a=JSON.parse(localStorage.getItem('nowify_auth_state')||'{}');"
        "return{status:!!a.status,hasRefresh:!!a.refreshToken};}"
        "catch(e){return{status:false,hasRefresh:false};}})())"
    )
    try:
        raw = cdp_eval(ws, expr)
        state = json.loads(raw) if raw else {}
    except Exception as e:
        log(f"DevTools eval failed ({e}) -> transient")
        return "transient"

    if state.get("status"):
        return "healthy"
    return "transient" if state.get("hasRefresh") else "expired"


def restart_chromium():
    if not RESTART_CMD:
        log("RESTART would fire but NOWIFY_RESTART_CMD is unset — not restarting.")
        return
    log(f"Restarting Chromium: {RESTART_CMD}")
    subprocess.run(RESTART_CMD, shell=True)


def main():
    state = get_state()
    log(f"state = {state}")

    if state in ("healthy", "expired"):
        # expired needs a human; never loop-restart on it.
        write_count(0)
        return 0

    # transient or unreachable -> count toward a restart
    count = read_count() + 1
    write_count(count)
    log(f"recoverable-bad check {count}/{FAIL_THRESHOLD}")

    if count >= FAIL_THRESHOLD:
        restart_chromium()
        write_count(0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
