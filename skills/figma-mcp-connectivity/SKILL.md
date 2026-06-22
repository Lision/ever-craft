---
name: figma-mcp-connectivity
description: Use when Codex needs to set up, diagnose, verify, or use Figma Desktop MCP for D2C frame extraction, including metadata, design context, variables, and screenshots from the selected Figma node.
---

# Figma MCP Connectivity

## Overview

Use this before any Figma-driven D2C workflow. Prove the local Figma server, Codex MCP registration, tool availability, and selected-node reads work before using Figma design data.

This skill only covers Figma MCP connectivity and extraction. Do not include application implementation, design-system coding, or product-specific data mapping here.

## Workflow

### 1. Run The Probe First

Run the bundled probe:

```bash
skills/figma-mcp-connectivity/scripts/figma_mcp_probe.sh
```

Run from the repository that contains the skill, or pass the absolute path to the script.

If the probe shows:

- `127.0.0.1:3845` is listening
- `codex mcp get figma-desktop` is registered
- `tools/list` includes `get_metadata`, `get_design_context`, `get_screenshot`, and `get_variable_defs`

then the environment is ready. Skip setup and go directly to [Read The Selected Frame](#5-read-the-selected-frame).

If any check fails, follow the relevant setup section below.

### 2. Start The Local Figma Server

Run:

```bash
lsof -nP -iTCP:3845 -sTCP:LISTEN || true
```

If empty, tell the user to:

1. Open Figma Desktop.
2. Open the target design file.
3. Switch to Dev Mode.
4. Enable the desktop MCP server in the right-side MCP server area.

Do not continue until `127.0.0.1:3845` is listening.

### 3. Register Codex MCP

Check:

```bash
codex mcp get figma-desktop 2>&1 || true
```

If missing, add it:

```bash
codex mcp add figma-desktop --url http://127.0.0.1:3845/mcp
codex mcp get figma-desktop
codex mcp list
```

Expected: `figma-desktop` is enabled and points to `http://127.0.0.1:3845/mcp`.

### 4. Bypass Local Proxy For Manual HTTP Checks

Shell environments may have `http_proxy`, `https_proxy`, or `all_proxy` set. If curl to localhost returns `502 Bad Gateway`, retry with:

```bash
curl --noproxy '*' ...
```

### 5. Discover Tools In The Current Session

If the current Codex session exposes MCP tools, use tool discovery for:

```text
figma mcp design node selection file dev mode metadata screenshot code
```

Expected tools include `get_design_context`, `get_metadata`, `get_screenshot`, and `get_variable_defs`.

If tool discovery returns nothing but the probe succeeds, explain that the current session did not load the newly registered MCP server. Continue with direct MCP HTTP calls only for validation, or ask the user to restart Codex so native tools load.

### 6. Read The Selected Frame

Ask the user to select one mobile page frame in Figma Desktop: the outer frame for a phone screen or mobile long page, not a button, text layer, group, entire page, or multiple nodes.

Call tools in this order:

1. `get_metadata` to confirm selected node id, name, dimensions, and hierarchy.
2. `get_design_context` for D2C reference code, assets, and contextual guidance.
3. `get_screenshot` for visual comparison.
4. `get_variable_defs` to check whether Figma variables expose tokens.

If using direct MCP HTTP, call `tools/call` with the current selection by omitting `nodeId`, or pass the node id returned by metadata.

`get_screenshot` provides the Figma baseline screenshot. It does not compare images by itself. For screenshot comparison, capture the generated app separately with browser tooling, then compare against the Figma PNG with a visual diff tool or manual review.

## Direct MCP Call Pattern

Use this pattern only when native Figma tools are unavailable in the current Codex session:

```bash
SESSION_ID=$(curl --noproxy '*' -sS -D - -o /tmp/figma-mcp-init.out \
  -X POST http://127.0.0.1:3845/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"codex-figma-check","version":"0.1.0"}}}' \
  | awk 'tolower($1)=="mcp-session-id:" {print $2}' | tr -d '\r')

curl --noproxy '*' -sS -X POST http://127.0.0.1:3845/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  --data '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}' >/tmp/figma-mcp-initialized.out || true

curl --noproxy '*' -sS -X POST http://127.0.0.1:3845/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "mcp-session-id: $SESSION_ID" \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

## Report Format

After the first successful read, report:

```text
Selected node:
Frame size:
Available Figma tools:
Variables:
Design context:
Screenshot:
Notable style tokens:
Implementation warnings:
Next step:
```

Implementation warnings should mention when Figma returns React + Tailwind reference code. Adapt it to the target project's stack; do not install Tailwind unless the user explicitly asks.

## Common Failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| No listener on 3845 | Figma Desktop MCP server is disabled | Enable Dev Mode MCP server in Figma Desktop |
| `codex mcp list` has no Figma server | Codex is not registered | Run `codex mcp add figma-desktop --url http://127.0.0.1:3845/mcp` |
| `curl` returns 502 | Proxy captured localhost traffic | Add `--noproxy '*'` |
| Tool discovery returns 0 tools | Current session loaded before MCP registration | Restart Codex or use direct MCP HTTP calls for validation |
| Metadata reads a tiny element | User selected an inner layer | Ask user to select the outer mobile frame |
