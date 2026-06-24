# Nowify kiosk watchdog + keyboard-free recovery (Raspberry Pi)

Keeps the desk "Now Playing" display alive without a power cycle (it runs on
PoE — no easy switch) and makes the periodic Spotify re-login doable from a
phone instead of a keyboard.

Deployed on the Pi at `192.168.0.205` (user `guntherbeam`, Raspbian 11
bullseye, LXDE/X11). The Nowify app itself is the Netlify build
(`scintillating-boba-a9f143.netlify.app`) shown in a Chromium kiosk — the repo
is **not** checked out on the Pi; these scripts are copied to `~/` there.

## How recovery works

`nowify-watchdog.py` runs every 5 min (cron) and reads kiosk state via the
Chromium DevTools Protocol (port 9222):

| State | Meaning | Action |
| --- | --- | --- |
| `healthy` | logged in / playing | nothing |
| `nowify_loggedout` | on Nowify's login screen (refresh token expired) | **clicks "Login with Spotify"**. If the Pi still has a Spotify session it's back instantly; if not, it lands on Spotify's login page → next row |
| `spotify_login` | on Spotify's own login page | overlays a **QR** that opens noVNC on your phone (see below) |
| `transient` / `unreachable` | browser hung / crashed | restarts Chromium after 3 consecutive bad checks |

It never reboot-loops on a logged-out state — those are handled by auto-login or
the QR, not by restarts.

### Why noVNC for the QR (not a login form)

Spotify's login is **reCAPTCHA-protected and multi-step**, so scripted
credential entry gets bot-flagged and fails. Instead the QR opens **noVNC**:
your phone becomes the Pi's screen and you complete the login interactively
(handles reCAPTCHA, Google/Apple/Facebook login, anything). The VNC password is
embedded in the QR (so scanning auto-connects) but is never rendered on screen.

Roughly every 6 months the refresh token expires; if the Pi's Spotify session
also lapsed you'll see the QR — scan it and sign in from your phone.

## What's installed on the Pi

- `~/nowify-watchdog.py` — the watchdog (cron, every 5 min).
- Cron: `*/5 * * * * DISPLAY=:0 XAUTHORITY=/home/guntherbeam/.Xauthority /usr/bin/python3 /home/guntherbeam/nowify-watchdog.py >> ~/nowify-watchdog.log 2>&1`
- Chromium autostart flags (in `~/.config/lxsession/LXDE-pi/autostart`):
  `--remote-debugging-port=9222 --remote-allow-origins=*`
- noVNC stack, also in LXDE autostart:
  - `@x11vnc -display :0 -auth ~/.Xauthority -rfbauth ~/.vnc/passwd -forever -shared -noxdamage -o ~/x11vnc.log`
  - `@websockify --web=/usr/share/novnc 6080 localhost:5900`
- VNC password: `~/.vnc/passwd` (set via `x11vnc -storepasswd`); plaintext copy
  the watchdog reads to build the QR URL at `~/.vnc/novnc_pw.txt`.
- Hidden mouse cursor (Chromium otherwise leaves the pointer parked on the
  kiosk screen, and there's no mouse to move it). Also in LXDE autostart:
  - `@unclutter --timeout 1`  (from the `unclutter-xfixes` package)
- Packages: `python3-websocket python3-qrcode x11vnc novnc websockify unclutter-xfixes`.

## Manual remote control anytime

Open `http://192.168.0.205:6080/vnc.html` on any device on the home wifi to see
and control the Pi's screen (enter the VNC password from `~/.vnc/novnc_pw.txt`).

## Security notes

- noVNC / x11vnc are **LAN-only** and password-protected. Don't forward ports
  6080/5900 to the internet.
- Nowify ships the Spotify **client secret** in its browser bundle (it's in the
  Pi's `localStorage` too). Consider rotating the secret and migrating to the
  PKCE flow (no secret) — tracked separately.

## Logs

`~/nowify-watchdog.log`, `~/x11vnc.log`, `~/websockify.log` on the Pi.
