---
name: pa-enable
description: >
  Enable/disable flows and patch kind:Skills for Copilot Studio compatibility.
  USE FOR: "enable flow", "start flow", "disable flow", "fix kind",
  "flows disabled after push", "flows broken after CPS push",
  "re-enable flows", "post-push recovery", "kind:Skills".
  DO NOT USE FOR: diagnosing issues (use pa-health first),
  importing new flows (use pa-import).
---

# Skill: Enable — Re-enable Flows and Fix kind:Skills

**Critical context:** After every Copilot Studio LSP push (`manage-agent` push), ALL category-5 cloud flows in the environment get disabled. This skill re-enables them and patches the `kind` property for CPS compatibility.

This is the most frequently used skill in the plugin. If a user says "I just pushed my agent and flows stopped working," this is always the answer.

---

## Enable All Disabled Flows

```bash
python scripts/enable_flow.py --enable --dataverse-url https://org123.crm.dynamics.com
```

Or, if `DATAVERSE_URL` is set:

```bash
python scripts/enable_flow.py --enable
```

This finds all disabled category-5 flows (statecode = 1) and enables them by setting statecode back to 0 via the Dataverse Web API.

---

## Enable Specific Flows Only

```bash
python scripts/enable_flow.py --enable --flow-ids a1b2c3d4-e5f6-7890-abcd-ef1234567890,b2c3d4e5-f6a7-8901-bcde-f12345678901
```

Comma-separated list of workflow IDs. Only these flows will be enabled.

---

## Fix kind:Skills

```bash
python scripts/enable_flow.py --fix-kind --dataverse-url https://org123.crm.dynamics.com
```

Patches the `kind` property on triggers and Response actions in the Flow API definition to `"Skills"`. This is required for Copilot Studio to discover and invoke the flow.

### What the kind Patch Does

For each flow, the script performs a three-step sequence via the Flow API:

1. **Stop** the flow (POST to `/stop`)
2. **PATCH** the flow definition — sets `kind: "Skills"` on:
   - The trigger (e.g., `triggers.manual.kind = "Skills"`)
   - All Response actions (e.g., `actions.Response.kind = "Skills"`)
3. **Start** the flow (POST to `/start`)

The stop → patch → start sequence is required because the Flow API does not allow definition changes on a running flow.

### Fix kind on Specific Flows

```bash
python scripts/enable_flow.py --fix-kind --flow-ids a1b2c3d4-...,b2c3d4e5-...
```

---

## Combined: Post-Push Recovery (Most Common Usage)

After a Copilot Studio push, run both operations together:

```bash
python scripts/enable_flow.py --enable --fix-kind
```

This is the standard post-push recovery command. It:
1. Enables all disabled category-5 flows
2. Patches kind:Skills on all triggers and Response actions

**This should be run after EVERY Copilot Studio push.** Consider it mandatory.

---

## Disable Flows

To disable specific flows:

```bash
python scripts/enable_flow.py --disable --flow-ids a1b2c3d4-...,b2c3d4e5-...
```

To disable all category-5 flows (use with caution):

```bash
python scripts/enable_flow.py --disable
```

---

## Options Reference

| Flag | Description |
|------|-------------|
| `--enable` | Enable disabled flows (set statecode = 0) |
| `--disable` | Disable flows (set statecode = 1) |
| `--fix-kind` | Patch kind:Skills on triggers and Response actions via Flow API |
| `--flow-ids {id1,id2,...}` | Operate on specific flows only (comma-separated) |
| `--dataverse-url {url}` | Dataverse environment URL (or set `DATAVERSE_URL`) |

---

## How It Works Under the Hood

### Enable/Disable (Dataverse Web API)

```
PATCH /api/data/v9.2/workflows({workflowid})
Content-Type: application/json

{"statecode": 0}   // 0 = enabled, 1 = disabled
```

### kind Patch (Flow Management API)

```
POST https://{flow-api-host}/providers/Microsoft.ProcessSimple/environments/{env}/flows/{flowid}/stop
PATCH https://{flow-api-host}/providers/Microsoft.ProcessSimple/environments/{env}/flows/{flowid}
POST https://{flow-api-host}/providers/Microsoft.ProcessSimple/environments/{env}/flows/{flowid}/start
```

The PATCH body updates the flow definition with `kind: "Skills"` on the trigger and all Response actions.

---

## Troubleshooting

### "Flow enabled but CPS still can't invoke it"

Run `pa-health` to check:
- Is `kind:Skills` set correctly? → `--fix-kind`
- Does the flow have a `resourcecontainerid`? → If not, re-import with `pa-import`
- Are there boolean outputs? → Manual fix required (see `pa-health`)

### "Flow API PATCH fails with 403"

Your account may lack Flow API permissions. Ensure you have the Environment Maker or System Administrator role in the Power Platform environment.

### "Flow won't start after kind patch"

The flow definition may have validation errors. Check the Flow API error response for details. Common causes:
- Invalid connection references (connections were deleted or expired)
- Missing environment variables
- Schema validation failures in the definition

Export the flow (`pa-export`) and inspect the definition for issues.
