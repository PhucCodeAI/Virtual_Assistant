#!/bin/sh
# Entrypoint cho dev container.
#
# Vấn đề: bind mount ./UI:/app từ Windows host mang node_modules (Windows
# binaries) vào Linux container → Vite/Rolldown crash vì thiếu native
# binding Linux. Anonymous volume không cứu được (Docker init volume từ
# content sau bind mount).
#
# Giải pháp: check nếu binding Linux thiếu → cài lại trong container.
# Named volume persist node_modules giữa các lần restart → không cài lại
# mỗi lần start.
set -e

# Marker: binding Linux của rolldown — có khi npm ci chạy đúng platform.
LINUX_BINDING_MARKER="node_modules/@rolldown/binding-linux-x64-gnu/package.json"

if [ ! -f "$LINUX_BINDING_MARKER" ]; then
  echo "[entrypoint] Native binding mismatch (Linux binding thiếu)."
  echo "[entrypoint] Chạy npm ci để cài lại dependencies cho container..."
  npm ci --no-audit --no-fund
  echo "[entrypoint] npm ci xong."
fi

exec "$@"