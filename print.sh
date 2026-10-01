#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Offline tools and help require only the Python 3 standard library.
case "${1:-}" in
    inspect|slice|-h|--help) exec python3 "$SCRIPT_DIR/src/bee_cli.py" "$@" ;;
esac
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/src/bee_cli.py" "$@"
fi
if python3 -c 'import usb.core' >/dev/null 2>&1; then
    exec python3 "$SCRIPT_DIR/src/bee_cli.py" "$@"
fi
echo "Python 3 PyUSB is missing. Run: cd "$SCRIPT_DIR" && uv sync" >&2
exit 1
