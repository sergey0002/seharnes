#!/usr/bin/env bash
# Start Chrome for Testing chromedriver on :9515 (WSL, Codeception without Selenium Grid).
# Docs: .doc/qa/browser-setup.md
#
# Браузер открывается ВИДИМЫМ окном через WSLg (DISPLAY=:0).
# Не добавляй --headless сюда и в chrome args suite.
#
# Codeception часто крутится в docker (php:8.3) на Docker Desktop —
# там --network host не видит порты WSL. Подключение идёт на
# host.docker.internal:9515.
#
# ChromeDriver 111+ отклоняет нелокальный Host ("Rejecting request with
# non-local host: host.docker.internal:9515"), поэтому драйвер слушает
# 127.0.0.1:9516, а на 127.0.0.1:9515 поднимается relay, который
# переписывает Host на 127.0.0.1:9516. Docker видит relay через
# host.docker.internal:9515.
set -euo pipefail

ROOT="${HOME}/.local/chrome-for-testing"
DEPS_LIB="${HOME}/.local/chrome-deps/root/usr/lib/x86_64-linux-gnu"
DEPS_LIB2="${HOME}/.local/chrome-deps/root/lib/x86_64-linux-gnu"
DRIVER="${ROOT}/chromedriver-linux64/chromedriver"
LOG="${ROOT}/chromedriver-9516.log"
DRIVER_PORT=9516
RELAY_PORT=9515
RELAY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/chromedriver-host-relay.py"
RELAY_LOG="${ROOT}/chromedriver-relay-9515.log"

if [[ ! -x "${DRIVER}" ]]; then
  echo "ERROR: chromedriver not found or not executable: ${DRIVER}" >&2
  echo "See .doc/qa/browser-setup.md" >&2
  exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
  if [[ -S /tmp/.X11-unix/X0 ]]; then
    export DISPLAY=:0
  else
    echo "ERROR: DISPLAY не задан и /tmp/.X11-unix/X0 нет — окно Chrome не появится." >&2
    echo "Нужен WSLg или внешний X-сервер. См. .doc/qa/browser-setup.md" >&2
    exit 1
  fi
fi

export LD_LIBRARY_PATH="${DEPS_LIB}:${DEPS_LIB2}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

pkill -f "${ROOT}/chromedriver-linux64/chromedriver" 2>/dev/null || true
pkill -f "chromedriver-host-relay.py" 2>/dev/null || true
sleep 0.3

# allowed-ips не задаём: пустое значение запрещало все адреса.
# Драйвер закрыт loopback-релеем, наружу смотрит только 9515.
nohup env DISPLAY="${DISPLAY}" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
  "${DRIVER}" \
  --port=${DRIVER_PORT} \
  --allowed-origins=* \
  --url-base=/wd/hub \
  >"${LOG}" 2>&1 &

sleep 0.8
if ! curl -fsS "http://127.0.0.1:${DRIVER_PORT}/wd/hub/status" >/dev/null; then
  echo >&2
  echo "ERROR: chromedriver did not become ready. Log: ${LOG}" >&2
  tail -n 40 "${LOG}" >&2 || true
  exit 1
fi

if [[ ! -f "${RELAY}" ]]; then
  echo "ERROR: relay not found: ${RELAY}" >&2
  exit 1
fi
nohup python3 "${RELAY}" --listen-port ${RELAY_PORT} --upstream-port ${DRIVER_PORT} \
  >"${RELAY_LOG}" 2>&1 &

sleep 0.5
if ! curl -fsS "http://127.0.0.1:${RELAY_PORT}/wd/hub/status"; then
  echo >&2
  echo "ERROR: relay did not become ready. Log: ${RELAY_LOG}" >&2
  tail -n 40 "${RELAY_LOG}" >&2 || true
  exit 1
fi
echo
echo "chromedriver OK pid=$(pgrep -f "${ROOT}/chromedriver-linux64/chromedriver" | head -1) port=${DRIVER_PORT} log=${LOG}"
echo "relay OK pid=$(pgrep -f "chromedriver-host-relay.py" | head -1) port=${RELAY_PORT} log=${RELAY_LOG}"
echo "DISPLAY=${DISPLAY} — Chrome будет видимым окном на экране (headed)."
