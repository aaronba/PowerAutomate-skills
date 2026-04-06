---
name: pa-health
description: >
  Health check for Power Automate flows — finds disabled flows, missing kind:Skills,
  boolean outputs, and unregistered flows.
  USE FOR: "check flows", "flow health", "diagnose flows", "flow issues",
  "why is my flow broken", "flow not working in CPS", "audit flows",
  "find broken flows", "flow outputs not working".
  DO NOT USE FOR: enabling flows (use pa-enable after diagnosis),
  importing flows (use pa-import).
---

# Skill: Health Check — Diagnose Flow Issues

Runs a comprehensive health check on all Power Automate cloud flows in a Dataverse environment. Identifies common issues that break Copilot Studio integration.

---

## Basic Usage

```bash
python scripts/health_check.py --dataverse-url https://org123.crm.dynamics.com
```

Or, if `DATAVERSE_URL` is set:

```bash
python scripts/health_check.py
```

---

## Checks Performed

The health check inspects every category-5 flow and reports issues in five categories:

### 1. Disabled Flows (statecode != 0)

Flows with `statecode = 1` are disabled and cannot be invoked. This commonly happens after a Copilot Studio push (see Gotcha 1 in `pa-overview`).

```
[WARN] Disabled flow: "Handle Customer Request" (a1b2c3d4-...)
       statecode=1, statuscode=2
```

**Fix:** `python scripts/enable_flow.py --enable`

### 2. Missing resourcecontainer (Not Registered with Flow API)

Flows without a `resourcecontainerid` exist only as Dataverse records — they have no runtime registration and cannot execute.

```
[ERROR] Unregistered flow: "Process Order" (b2c3d4e5-...)
        No resourcecontainerid — flow cannot run
```

**Fix:** Re-import the flow with `pa-import` to perform both Dataverse and Flow API registration.

### 3. Trigger Missing kind:Skills

For flows invoked by Copilot Studio, the trigger's `kind` property in the Flow API definition must be `"Skills"`. If missing, CPS cannot discover or invoke the flow.

```
[WARN] Trigger kind missing: "Send Notification" (c3d4e5f6-...)
       Trigger kind is "Http" — should be "Skills" for CPS
```

**Fix:** `python scripts/enable_flow.py --fix-kind --flow-ids c3d4e5f6-...`

### 4. Response Actions Missing kind:Skills

Same as trigger kind, but for Response actions. If missing, CPS cannot read the flow's output values.

```
[WARN] Response kind missing: "Handle Request" (d4e5f6a7-...)
       Response action "Response" kind is "Http" — should be "Skills"
```

**Fix:** `python scripts/enable_flow.py --fix-kind --flow-ids d4e5f6a7-...`

### 5. Boolean Outputs in Response Schemas

**This is the most dangerous issue.** If any Response action's output schema contains a property with `"type": "boolean"`, ALL output mappings from that flow to Copilot Studio will fail silently. CPS cannot deserialize boolean values.

```
[ERROR] Boolean output detected: "Validate Customer" (e5f6a7b8-...)
        Response action "Response" has boolean property "isValid"
        THIS BREAKS ALL CPS OUTPUT MAPPINGS FOR THIS FLOW
```

**Fix:** This requires a manual edit — boolean outputs cannot be auto-fixed without changing the contract:
1. Export the flow: `python scripts/export_flow.py --flow-id e5f6a7b8-...`
2. Open `workflow.json`
3. Find the Response action's output schema
4. Change `"type": "boolean"` to `"type": "string"` (use `"true"`/`"false"` as values)
   — or change to `"type": "integer"` (use `1`/`0` as values)
5. Update any Compose/variable actions that set these outputs to match the new type
6. Re-import: `python scripts/import_flow.py --flow-json workflow.json --name "Validate Customer"`
7. Update the Copilot Studio topic to expect strings instead of booleans

---

## Auto-Fix Mode

```bash
python scripts/health_check.py --fix --dataverse-url https://org123.crm.dynamics.com
```

With `--fix`, the script automatically:
- **Enables** disabled flows (sets statecode to 0)
- **Patches kind:Skills** on triggers and Response actions via Flow API

**What `--fix` does NOT do:**
- Fix boolean outputs (requires manual schema change — see above)
- Register unregistered flows (use `pa-import` for that)

---

## Example Output

```
=== Power Automate Health Check ===
Environment: https://org123.crm.dynamics.com

Checking 8 cloud flows...

[OK]    Handle Customer Request    (a1b2c3d4-...)
[OK]    Process Order              (b2c3d4e5-...)
[WARN]  Send Notification          (c3d4e5f6-...)  — disabled
[WARN]  Old Integration            (d4e5f6a7-...)  — disabled, trigger kind missing
[ERROR] Validate Customer          (e5f6a7b8-...)  — boolean output "isValid"
[OK]    Approval Workflow          (f6a7b8c9-...)
[ERROR] Orphan Flow                (a7b8c9d0-...)  — no resourcecontainer
[WARN]  Feedback Handler           (b8c9d0e1-...)  — Response kind missing

Summary:
  OK:     3
  WARN:   3 (fixable with --fix)
  ERROR:  2 (manual intervention required)
```

---

## When to Run Health Checks

| Scenario | Command |
|----------|---------|
| After any Copilot Studio push | `python scripts/health_check.py --fix` |
| Flow outputs not appearing in CPS | `python scripts/health_check.py` (look for booleans/kind issues) |
| After solution import | `python scripts/health_check.py --fix` |
| Routine audit | `python scripts/health_check.py` |
| After portal edits to flows | `python scripts/health_check.py` (kind may have been reset) |
