#!/usr/bin/env bash
# Run this ON THE PI. It reports how the Nowify kiosk is launched so the
# watchdog can be wired up (restart command + where to add the debug-port flag).
echo "=== OS ==="
grep -E "^(PRETTY_NAME|VERSION_CODENAME)=" /etc/os-release

echo; echo "=== running chromium (process + flags) ==="
ps -eo pid,cmd | grep -i '[c]hromium' || echo "chromium not running"

echo; echo "=== chromium binary ==="
command -v chromium-browser chromium 2>/dev/null || echo "no chromium in PATH"

echo; echo "=== systemd units mentioning chromium/kiosk/nowify ==="
systemctl list-units --all --type=service 2>/dev/null | grep -iE 'chromium|kiosk|nowify' || echo "none (system)"
systemctl --user list-units --all --type=service 2>/dev/null | grep -iE 'chromium|kiosk|nowify' || echo "none (user)"

echo; echo "=== autostart files mentioning chromium ==="
grep -rIl chromium \
  ~/.config/autostart/ \
  ~/.config/lxsession/ \
  /etc/xdg/lxsession/ \
  ~/.config/wayfire.ini \
  ~/.config/labwc/autostart \
  ~/.config/labwc/ \
  /etc/xdg/autostart/ 2>/dev/null || echo "none found in usual spots"

echo; echo "=== debug port 9222 already listening? ==="
(ss -ltnp 2>/dev/null | grep -q ':9222' && echo "yes") || echo "no"

echo; echo "=== websocket-client available? ==="
python3 -c "import websocket; print('yes')" 2>/dev/null || echo "no (sudo apt install -y python3-websocket)"
