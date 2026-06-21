---
name: figma-mcp-connectivity
description: Use when Codex needs Figma Desktop MCP for design-to-code work, including MCP setup checks, selected frame extraction, or generating a runnable MiniApp page from Figma with @everly/miniapp-uidesign and @everly/miniapp-network.
---

# Figma MCP Connectivity

## Overview

Use this before any Figma-driven D2C workflow. Prove the local Figma server, Codex MCP registration, and selected-node reads work before generating code.

For the implementation phase that creates `@everly/miniapp-uidesign` and a runnable nutrition MiniApp page, read [references/nutrition-miniapp-generation.md](references/nutrition-miniapp-generation.md) after the Figma frame has been extracted.

## Workflow

### 1. Check The Local Figma Server

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

### 2. Register Codex MCP

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

### 3. Bypass Local Proxy For Manual HTTP Checks

Shell environments may have `http_proxy`, `https_proxy`, or `all_proxy` set. If curl to localhost returns `502 Bad Gateway`, retry with:

```bash
curl --noproxy '*' ...
```

Use the bundled probe for a deterministic check:

```bash
skills/figma-mcp-connectivity/scripts/figma_mcp_probe.sh
```

Run from the repository that contains the skill, or pass the absolute path to the script.

### 4. Discover Tools

If the current Codex session exposes MCP tools, use tool discovery for:

```text
figma mcp design node selection file dev mode metadata screenshot code
```

Expected tools include `get_design_context`, `get_metadata`, `get_screenshot`, and `get_variable_defs`.

If tool discovery returns nothing but the probe succeeds, explain that the current session did not load the newly registered MCP server. Continue with direct MCP HTTP calls only for validation, or ask the user to restart Codex so native tools load.

### 5. Read The Selected Frame

Ask the user to select one mobile page frame in Figma Desktop: the outer frame for a phone screen or mobile long page, not a button, text layer, group, entire page, or multiple nodes.

Call tools in this order:

1. `get_metadata` to confirm selected node id, name, dimensions, and hierarchy.
2. `get_design_context` for D2C reference code, assets, and contextual guidance.
3. `get_screenshot` for visual comparison.
4. `get_variable_defs` to check whether Figma variables expose tokens.

If using direct MCP HTTP, call `tools/call` with the current selection by omitting `nodeId`, or pass the node id returned by metadata.

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

## MiniApp D2C Generation

After connectivity and selected-frame extraction pass:

1. Extract visual tokens from Figma context, screenshot, and variables. If `get_variable_defs` returns `{}`, treat observed styles as extracted tokens.
2. Identify whether the visual family already exists in `@everly/miniapp-uidesign`. Reuse an exact match; ask the user before creating a new family when it is close but not identical; create a new family only for clearly distinct styles.
3. Map visible health concepts to `@everly/miniapp-network` Health KV keys before coding UI. Unsupported data must be replaced with the closest valid key, derived conservatively from valid keys, or removed with layout adjustment.
4. Keep reusable visual decisions in `@everly/miniapp-uidesign`; keep page orchestration and network calls in `src/miniapp/App.tsx`.
5. Verify with install, type/lint, static build, and local browser or HTTP checks.

Read [references/nutrition-miniapp-generation.md](references/nutrition-miniapp-generation.md) for the concrete nutrition workflow, package structure, mapping rules, and validation checklist.

## Common Failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| No listener on 3845 | Figma Desktop MCP server is disabled | Enable Dev Mode MCP server in Figma Desktop |
| `codex mcp list` has no Figma server | Codex is not registered | Run `codex mcp add figma-desktop --url http://127.0.0.1:3845/mcp` |
| `curl` returns 502 | Proxy captured localhost traffic | Add `--noproxy '*'` |
| Tool discovery returns 0 tools | Current session loaded before MCP registration | Restart Codex or use direct MCP HTTP calls for validation |
| Metadata reads a tiny element | User selected an inner layer | Ask user to select the outer mobile frame |
