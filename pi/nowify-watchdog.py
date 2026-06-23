#!/usr/bin/env python3
"""
Nowify kiosk watchdog (v2) — keyboard-free recovery.

Reads kiosk state via the Chromium DevTools Protocol and acts:

  healthy            logged in / playing                 -> nothing
  nowify_loggedout   on the Nowify login screen, refresh -> AUTO RE-LOGIN: click
                     token gone (Spotify policy)            "Login with Spotify".
                                                            Works with no human as
                                                            long as the Pi is still
                                                            signed into Spotify.
  spotify_login      kicked out to Spotify's own login   -> overlay a QR pointing at
                     page (Spotify session also expired)    the on-Pi login server, so
                                                            the phone can type creds.
  transient/unreach  browser hung / crashed              -> restart Chromium after
                                                            FAIL_THRESHOLD checks.

Never loop-restarts Chromium on a logged-out/expired state — those are handled
by auto-login or the QR, not by reboots.

Deps: python3-websocket, python3-qrcode. Chromium must run with
  --remote-debugging-port=9222 --remote-allow-origins=*
"""

import json, os, socket, subprocess, sys, time, urllib.request

DEBUG_PORT = 9222
NOVNC_PORT = 6080
NOVNC_PW_FILE = os.path.expanduser("~/.vnc/novnc_pw.txt")
APP_HINT = "nowify"
FAIL_THRESHOLD = 3
APP_URL = "https://scintillating-boba-a9f143.netlify.app/"
RESTART_CMD = ("pkill -f chromium-browser; sleep 2; "
    "/usr/bin/chromium-browser --force-renderer-accessibility "
    "--enable-remote-extensions --enable-pinch "
    "--remote-debugging-port=9222 --remote-allow-origins=* "
    "--kiosk %s >/dev/null 2>&1 &" % APP_URL)
RESTART_COUNT = os.path.expanduser("~/.nowify-watchdog.count")


def log(m): print("[nowify-watchdog]", m, flush=True)

def _rc(path):
    try: return int(open(path).read().strip())
    except Exception: return 0

def _wc(path, n):
    try: open(path, "w").write(str(n))
    except Exception as e: log("count write failed: %s" % e)

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

def cdp_pages():
    data = json.load(urllib.request.urlopen("http://localhost:%d/json" % DEBUG_PORT, timeout=5))
    return [t for t in data if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]

def pick(pages):
    for t in pages:
        u = (t.get("url","") + " " + t.get("title","")).lower()
        if "accounts.spotify.com" in u or APP_HINT in u:
            return t["webSocketDebuggerUrl"], t.get("url","")
    return pages[0]["webSocketDebuggerUrl"], pages[0].get("url","")

def cdp_eval(ws_url, expr):
    from websocket import create_connection
    ws = create_connection(ws_url, timeout=6)
    try:
        ws.send(json.dumps({"id":1,"method":"Runtime.evaluate",
            "params":{"expression":expr,"returnByValue":True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == 1:
                return m.get("result",{}).get("result",{}).get("value")
    finally:
        ws.close()

def detect():
    try:
        pages = cdp_pages()
    except Exception as e:
        log("DevTools unreachable (%s)" % e); return ("unreachable", None, None)
    if not pages:
        return ("unreachable", None, None)
    ws, url = pick(pages)
    if "accounts.spotify.com" in url:
        return ("spotify_login", ws, url)
    expr = ("JSON.stringify((function(){try{"
            "var a=JSON.parse(localStorage.getItem('nowify_auth_state')||'{}');"
            "return{status:!!a.status,btn:!!document.querySelector('.authorise__button')};"
            "}catch(e){return{status:false,btn:false};}})())")
    try:
        s = json.loads(cdp_eval(ws, expr) or "{}")
    except Exception as e:
        log("eval failed (%s)" % e); return ("transient", ws, url)
    if s.get("status"): return ("healthy", ws, url)
    if s.get("btn"):    return ("nowify_loggedout", ws, url)
    return ("transient", ws, url)

def auto_login(ws):
    return cdp_eval(ws, "(function(){var b=document.querySelector('.authorise__button');"
                        "if(b){b.click();return 'clicked';}return 'no-button';})()")

def qr_svg(text):
    import io, qrcode
    import qrcode.image.svg as svg
    b = io.BytesIO()
    qrcode.make(text, image_factory=svg.SvgPathImage).save(b)
    return b.getvalue().decode()

def inject_qr(ws, svg, caption):
    # built with concatenation (no % operator) so the JS '100%' literals are safe
    js = ("(function(svg,cap){"
      "var id='nowify-qr-overlay';"
      "var old=document.getElementById(id); if(old) old.remove();"
      "var d=document.createElement('div'); d.id=id; var s=d.style;"
      "s.position='fixed'; s.left='0'; s.top='0'; s.right='0'; s.bottom='0';"
      "s.zIndex='2147483647'; s.background='rgba(0,0,0,0.93)'; s.display='flex';"
      "s.flexDirection='column'; s.alignItems='center'; s.justifyContent='center';"
      "s.fontFamily='sans-serif'; s.color='#fff';"
      "function line(t,sz,op,mb){var e=document.createElement('div');"
      "e.style.fontSize=sz; e.style.opacity=op; e.style.marginBottom=mb;"
      "e.style.textAlign='center'; e.textContent=t; return e;}"
      "var q=document.createElement('div'); q.style.background='#fff';"
      "q.style.padding='16px'; q.style.borderRadius='12px';"
      "q.style.width='300px'; q.style.height='300px'; q.innerHTML=svg;"
      "var qs=q.querySelector('svg'); if(qs){qs.style.width='100%'; qs.style.height='100%';}"
      "d.appendChild(line('Spotify sign-in needed','30px','1','16px'));"
      "d.appendChild(line('Scan to sign in from your phone','18px','0.8','24px'));"
      "d.appendChild(q);"
      "d.appendChild(line(cap,'14px','0.55','18px'));"
      "var btn=document.createElement('button');"
      "btn.textContent='I am signing in \\u2192';"
      "btn.style.padding='12px 20px'; btn.style.fontSize='15px'; btn.style.border='0';"
      "btn.style.borderRadius='22px'; btn.style.background='#1db954'; btn.style.color='#fff';"
      "btn.onclick=function(){try{localStorage.setItem('nowify_qr_dismissed',String(Date.now()));}catch(e){} d.remove();};"
      "d.appendChild(btn);"
      "document.body.appendChild(d); return 'ok';"
      "})(" + json.dumps(svg) + "," + json.dumps(caption) + ")")
    return cdp_eval(ws, js)

def novnc_url():
    # noVNC URL drives the Pi's own screen from the phone (handles reCAPTCHA).
    try:
        pw = open(NOVNC_PW_FILE).read().strip()
    except Exception:
        pw = ""
    u = "http://%s:%d/vnc.html?autoconnect=true&resize=scale" % (lan_ip(), NOVNC_PORT)
    return u + ("&password=" + pw if pw else "")

def show_qr(ws):
    url = novnc_url()  # contains the VNC password; encoded in the QR but never shown as text
    try:
        r = inject_qr(ws, qr_svg(url), "Scan with your phone camera")
        log("stuck on Spotify login -> QR to noVNC %s:%d (%s)" % (lan_ip(), NOVNC_PORT, r))
    except Exception as e:
        log("QR inject failed (%s)" % e)

def maybe_show_qr(ws):
    # Don't re-cover the screen if the QR is already up, or if the user dismissed
    # it recently (they're signing in via noVNC and need the form unobscured).
    try:
        g = json.loads(cdp_eval(ws,
            "(function(){var o=!!document.getElementById('nowify-qr-overlay');"
            "var d=parseInt(localStorage.getItem('nowify_qr_dismissed')||'0',10);"
            "return JSON.stringify({o:o,recent:!!(d&&(Date.now()-d)<1200000)});})()") or "{}")
    except Exception:
        g = {}
    if g.get("o"):
        log("QR already shown"); return
    if g.get("recent"):
        log("QR dismissed recently — leaving form visible"); return
    show_qr(ws)

def restart_chromium():
    log("restarting chromium"); subprocess.run(RESTART_CMD, shell=True)

def main():
    st, ws, url = detect()
    log("state = %s  url=%s" % (st, url))

    if st == "healthy":
        _wc(RESTART_COUNT, 0); return 0

    if st == "nowify_loggedout":
        # Click "Login with Spotify". If the Pi still has a Spotify session this
        # lands us back logged in; if not, it lands on Spotify's login page and
        # we show the QR so a phone can supply credentials.
        log("auto re-login: %s" % auto_login(ws))
        time.sleep(5)
        st, ws, url = detect()
        log("after click: state = %s" % st)

    if st == "spotify_login":
        maybe_show_qr(ws); _wc(RESTART_COUNT, 0); return 0

    if st == "healthy":
        _wc(RESTART_COUNT, 0); return 0

    # transient / unreachable
    n = _rc(RESTART_COUNT) + 1; _wc(RESTART_COUNT, n)
    log("recoverable-bad %d/%d" % (n, FAIL_THRESHOLD))
    if n >= FAIL_THRESHOLD:
        restart_chromium(); _wc(RESTART_COUNT, 0)
    return 0

if __name__ == "__main__":
    sys.exit(main())
