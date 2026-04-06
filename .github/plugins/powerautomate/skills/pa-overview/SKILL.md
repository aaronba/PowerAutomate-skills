---
name: pa-overview
description: >
  Core rules and routing for Power Automate flow management.
  Loaded automatically before other PA skills.
  USE FOR: any request involving Power Automate, cloud flows, workflow, flow management,
  "how do I", "which skill", "where do I start", "help with flows".
  This skill must be loaded before any other PA skill.
---

# Skill: Overview — Power Automate Flow Management

This skill provides cross-cutting context for managing Power Automate cloud flows via Dataverse and the Flow Management API. Per-task routing is handled by each skill's frontmatter triggers — not duplicated here.

---

## Hard Rules — Read These First

### 1. Two-API Architecture

Power Automate flows require **two separate APIs** working together:

| API | Base URL | Purpose |
|-----|----------|---------|
| **Dataverse Web API** | `{DATAVERSE_URL}/api/data/v9.2/` | CRUD on the `workflow` entity — contains the flow's `clientdata` (Logic Apps JSON definition), state, category, and solution membership |
| **Flow Management API** | `https://{host}/providers/Microsoft.ProcessSimple/` | Runtime registration, start/stop, definition PATCH, trigger management — the engine that actually runs the flow |

Both APIs are needed for full lifecycle management. Dataverse owns the record; the Flow API owns the runtime. A flow that exists only in Dataverse (no `resourcecontainer`) cannot run. A flow registered only in the Flow API has no solution membership.

### 2. Cloud Support

| Cloud | Dataverse suffix | Flow API host | Flow scope |
|-------|------------------|---------------|------------|
| **Public** | `.crm.dynamics.com` | `api.flow.microsoft.com` | `https://service.flow.microsoft.com/.default` |
| **GCC** | `.crm9.dynamics.com` | `gov.api.flow.microsoft.us` | `https://gov.service.flow.microsoft.us/.default` |
| **GCC-High** | `.crm.microsoftdynamics.us` | `high.api.flow.microsoft.us` | `https://high.service.flow.microsoft.us/.default` |

Cloud is auto-detected from `DATAVERSE_URL` or can be set explicitly via `CPS_CLOUD`.

### 3. Python Only — No Exceptions

All scripts and automation MUST use **Python**. This plugin's toolchain — `scripts/flow_auth.py`, all skill scripts — is Python-based.

**NEVER** use Node.js, JavaScript, PowerShell, or any other language for flow operations. If you find yourself about to run `npm` or create a `.js` file, STOP.

### 4. Use the Scripts, Don't Improvise

Each skill documents a specific, tested sequence of steps referencing scripts in `scripts/`. Follow them. If a skill says "run this script," run that script — do not substitute a raw HTTP call or invent an alternative.

---

## Key Gotchas — Memorize These

These are the most common failure modes. Agents must internalize all five.

### Gotcha 1: Copilot Studio Push Disables ALL Flows

After every Copilot Studio LSP push (`manage-agent` push), **all category-5 flows in the environment get disabled** (statecode set to 1). This is by design — CPS redeploys the solution and disables everything.

**Fix:** Run `pa-enable` after every push. This is not optional.

### Gotcha 2: kind:Skills Resets After Import/Push/Portal Edits

The `kind` property on flow triggers and Response actions must be `"Skills"` for Copilot Studio to invoke the flow. But this value is stripped during solution import, CPS push, and sometimes after editing in the portal.

**Fix:** Run `pa-enable --fix-kind` to re-patch kind on triggers and Response actions via the Flow API.

### Gotcha 3: Boolean Outputs in Response Schemas Break CPS

If a Response action's output schema contains a `"type": "boolean"` property, **ALL output mappings from that flow to Copilot Studio will fail silently**. CPS cannot deserialize boolean outputs.

**Fix:** Change boolean outputs to `"type": "string"` (with values `"true"`/`"false"`) or `"type": "integer"` (with values `1`/`0`). Use `pa-health` to detect this.

### Gotcha 4: Flow API Registration Is Separate from Dataverse Record

Creating a workflow record in Dataverse does NOT register it with the Flow API runtime. Both steps are required:
1. Dataverse `POST` creates the workflow record
2. Flow API `PATCH` registers the runtime definition

The `pa-import` script handles both steps automatically.

### Gotcha 5: Response Actions Need Dual kind Configuration

Response actions in flows invoked by Copilot Studio need:
- `kind: "PowerApp"` in the Dataverse `clientdata` JSON (the Logic Apps definition)
- `kind: "Skills"` in the Flow API definition (set via Flow API PATCH)

These are different representations of the same flow. The `pa-import` and `pa-enable` scripts handle this automatically.

---

## Prerequisites

```bash
pip install --upgrade azure-identity requests PowerPlatform-Dataverse-Client
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATAVERSE_URL` | Yes | Full URL, e.g., `https://org123.crm.dynamics.com` |
| `TENANT_ID` | Yes | Azure AD tenant ID |
| `CPS_CLOUD` | No | Override cloud detection: `public`, `gcc`, or `gcchigh` |
| `CLIENT_ID` | No | Service principal app ID (for non-interactive auth) |
| `CLIENT_SECRET` | No | Service principal secret (for non-interactive auth) |

Set these in `.env` at the repo root or as shell environment variables. All scripts read from both sources.

---

## Skill Routing Table

| User intent | Skill | Script |
|-------------|-------|--------|
| Connect, authenticate, set up | `pa-connect` | `scripts/flow_auth.py` (verify) |
| List flows, find flows | `pa-list` | `scripts/list_flows.py` |
| Export/download/backup flow | `pa-export` | `scripts/export_flow.py` |
| Import/create/deploy flow | `pa-import` | `scripts/import_flow.py` |
| Health check, diagnose issues | `pa-health` | `scripts/health_check.py` |
| Enable/disable, fix kind | `pa-enable` | `scripts/enable_flow.py` |
| "Flows broke after CPS push" | `pa-enable` | `scripts/enable_flow.py --enable --fix-kind` |
| "Flow outputs not working in CPS" | `pa-health` | `scripts/health_check.py` (check for booleans) |

---

## Authentication

All scripts use `scripts/flow_auth.py` which provides the `FlowAuth` class:

```python
from flow_auth import FlowAuth

auth = FlowAuth(dataverse_url="https://org123.crm.dynamics.com")
dv_token = auth.get_dataverse_token()   # For Dataverse Web API
flow_token = auth.get_flow_token()       # For Flow Management API
```

`FlowAuth` auto-detects cloud from the URL, supports both interactive and service principal auth, and handles authority differences for GCC/GCC-High.

---

## What This Plugin Covers

- Power Automate **cloud flows** (category 5) in Dataverse environments
- Listing, exporting, importing, enabling/disabling flows
- Health checks for Copilot Studio compatibility
- Post-push recovery (re-enable + fix kind)

It does **not** cover:
- Desktop flows (category 6)
- Canvas app flows
- Flow authoring/editing of Logic Apps actions (use the portal or VS Code extension)
- Connection management (use the portal)
- Power Automate approvals, business process flows, or other flow types
