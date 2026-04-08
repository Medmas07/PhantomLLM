#!/usr/bin/env sh
set -eu

mode="${PHANTOM_MODE:-api}"
model="${PHANTOM_MODEL:-openai_ui}"
browser="${PHANTOM_BROWSER:-camoufox}"
host="${PHANTOM_HOST:-0.0.0.0}"
port="${PHANTOM_PORT:-8000}"
headless_raw="${PHANTOM_HEADLESS:-true}"

headless_flag="--hide-browser"
case "$(printf "%s" "$headless_raw" | tr '[:upper:]' '[:lower:]')" in
  false|0|no)
    headless_flag="--show-browser"
    ;;
esac

case "$mode" in
  cli)
    exec python -m agent.main --cli --model "$model" --browser "$browser" "$headless_flag" "$@"
    ;;
  api|*)
    exec python -m agent.main --api --model "$model" --browser "$browser" "$headless_flag" --host "$host" --port "$port" "$@"
    ;;
esac

