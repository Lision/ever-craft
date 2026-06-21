#!/usr/bin/env bash
set -euo pipefail

endpoint="${FIGMA_MCP_ENDPOINT:-http://127.0.0.1:3845/mcp}"

echo "== Figma Desktop MCP probe =="
echo "endpoint: ${endpoint}"

echo
echo "== Port check =="
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:3845 -sTCP:LISTEN || true
else
  echo "lsof not found; skipping port check"
fi

echo
echo "== Codex MCP registration =="
if command -v codex >/dev/null 2>&1; then
  codex mcp get figma-desktop 2>&1 || true
else
  echo "codex CLI not found; skipping Codex MCP registration check"
fi

echo
echo "== MCP initialize =="
headers_file="$(mktemp)"
body_file="$(mktemp)"
trap 'rm -f "$headers_file" "$body_file" "$list_headers_file" "$list_body_file"' EXIT

curl --noproxy '*' -sS -D "$headers_file" -o "$body_file" \
  -X POST "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"figma-mcp-probe","version":"0.1.0"}}}'

status_line="$(head -n 1 "$headers_file" | tr -d '\r')"
session_id="$(awk 'tolower($1)=="mcp-session-id:" {print $2}' "$headers_file" | tr -d '\r')"
echo "$status_line"
echo "mcp-session-id: ${session_id:-missing}"

if [[ -z "${session_id}" ]]; then
  echo "ERROR: MCP initialize did not return mcp-session-id" >&2
  echo "Response body:" >&2
  sed -n '1,80p' "$body_file" >&2
  exit 1
fi

curl --noproxy '*' -sS -X POST "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $session_id" \
  --data '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}' >/dev/null || true

echo
echo "== MCP tools/list =="
list_headers_file="$(mktemp)"
list_body_file="$(mktemp)"
curl --noproxy '*' -sS -D "$list_headers_file" -o "$list_body_file" \
  -X POST "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $session_id" \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

head -n 1 "$list_headers_file" | tr -d '\r'
grep -o '"name":"[^"]*"' "$list_body_file" | sed 's/"name":"//; s/"$//' || true
