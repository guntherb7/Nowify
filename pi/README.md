# Nowify kiosk watchdog (Raspberry Pi)

Self-heals the Pi "Now Playing" display **without** a power cycle (handy when the
Pi runs on PoE and there's no easy switch). It restarts **Chromium only** — not
the whole OS.

## What it does — and the one thing it deliberately won't do

The watchdog reads Nowify's auth state out of the running Chromium kiosk over the
DevTools Protocol and classifies it:

| State | Meaning | Action |
| --- | --- | --- |
| logged in / playing | working | nothing |
| not logged in, **refresh token still stored** | transient: browser hung, boot-time network blip, mid-refresh | restart Chromium after 3 consecutive bad checks |
| not logged in, **no refresh token** | refresh token expired/revoked (Spotify's 6‑month policy) | **nothing** |

That last row is the important one. A restart **cannot** recover an expired
refresh token — that needs a human to click **"Login with Spotify"** once on the
Pi. Restarting on it would just loop forever, so the watchdog refuses to.
(This relies on the `invalid_grant` fix in `src/components/Authorise.vue`, which
clears the dead refresh token so "expired" is detectable.)

Expect to manually re-login at the Pi roughly every 6 months. Set a reminder.

## Requirements

1. **Chromium launched with remote debugging.** Add this flag to however the
   kiosk starts Chromium:

   ```
   --remote-debugging-port=9222
   ```

   (Bound to localhost; the watchdog runs on the Pi itself.)

2. **websocket-client** for Python:

   ```bash
   sudo apt install -y python3-websocket   # or: pip3 install websocket-client
   ```

3. This repo checked out on the Pi (paths below assume `/home/pi/Nowify`).

## Configure the restart command

Set `NOWIFY_RESTART_CMD` to whatever relaunches your kiosk. Pick the one that
matches your setup (run `pi/detect.sh` if unsure):

- Chromium started by a **systemd system service**:
  `sudo systemctl restart <your-kiosk-service>`
- Chromium started by a **systemd --user service**:
  `systemctl --user restart <your-kiosk-service>`
- Chromium started by **autostart with no supervisor** (it won't relaunch on its
  own, so the watchdog must relaunch it):
  `pkill -f chromium; sleep 2; <full chromium kiosk command> &`

Put it in `nowify-watchdog.service` (`Environment=NOWIFY_RESTART_CMD=...`).

## Install (systemd timer, runs every 5 min)

```bash
sudo cp /home/pi/Nowify/pi/nowify-watchdog.service /etc/systemd/system/
sudo cp /home/pi/Nowify/pi/nowify-watchdog.timer   /etc/systemd/system/
# edit the .service to set NOWIFY_RESTART_CMD first
sudo systemctl daemon-reload
sudo systemctl enable --now nowify-watchdog.timer
```

Check it:

```bash
systemctl status nowify-watchdog.timer
sudo systemctl start nowify-watchdog.service   # run once now
journalctl -u nowify-watchdog.service -n 20
```

## Tuning (env vars in the .service)

- `NOWIFY_FAIL_THRESHOLD` (default 3) — consecutive bad checks before restart.
- `NOWIFY_DEBUG_PORT` (default 9222).
- `NOWIFY_APP_HINT` (default `nowify`) — substring to pick the right tab.
