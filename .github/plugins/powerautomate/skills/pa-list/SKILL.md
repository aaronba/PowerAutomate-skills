---
name: pa-list
description: >
  List Power Automate cloud flows in a Dataverse environment.
  USE FOR: "list flows", "show flows", "what flows exist", "find flows",
  "which flows are enabled", "which flows are disabled", "flows for agent".
  DO NOT USE FOR: exporting flow definitions (use pa-export),
  enabling/disabling flows (use pa-enable).
---

# Skill: List — Show Cloud Flows in the Environment

Lists Power Automate cloud flows (category 5) by querying the Dataverse `workflow` entity. Shows flow name, ID, state, and solution membership.

---

## Basic Usage

```bash
python scripts/list_flows.py --dataverse-url https://org123.crm.dynamics.com
```

Or, if `DATAVERSE_URL` is set in `.env` or environment:

```bash
python scripts/list_flows.py
```

### Default Behavior

By default, lists only **enabled** flows (statecode = 0, category = 5). Output format:

```
Found 3 cloud flows:
  [enabled]  Handle Customer Request    (a1b2c3d4-e5f6-7890-abcd-ef1234567890)
  [enabled]  Process Order              (b2c3d4e5-f6a7-8901-bcde-f12345678901)
  [enabled]  Send Notification          (c3d4e5f6-a7b8-9012-cdef-123456789012)
```

---

## Options

### Show all flows (including disabled)

```bash
python scripts/list_flows.py --all
```

Output includes state indicator:

```
Found 5 cloud flows:
  [enabled]  Handle Customer Request    (a1b2c3d4-...)
  [enabled]  Process Order              (b2c3d4e5-...)
  [disabled] Send Notification          (c3d4e5f6-...)
  [disabled] Old Integration Flow       (d4e5f6a7-...)
  [enabled]  Approval Workflow          (e5f6a7b8-...)
```

### Filter by Copilot Studio agent (bot ID)

```bash
python scripts/list_flows.py --bot-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

This filters flows associated with a specific Copilot Studio agent by checking the `clientdata` for bot references. Useful when an environment has many flows and you only care about flows connected to a particular agent.

---

## What the Script Queries

The script queries the Dataverse `workflow` entity:

```
GET /api/data/v9.2/workflows?$filter=category eq 5&$select=workflowid,name,statecode,statuscode,clientdata,resourcecontainerid
```

- `category eq 5` = cloud flows (not desktop flows, BPFs, etc.)
- `statecode`: 0 = enabled, 1 = disabled
- `resourcecontainerid`: present if registered with Flow API; null if Dataverse-only
- `clientdata`: the full Logic Apps JSON definition (not returned in list, only in export)

---

## Example: Quick Check After CPS Push

After a Copilot Studio push, use `--all` to see which flows got disabled:

```bash
python scripts/list_flows.py --all
```

If flows show as `[disabled]`, use `pa-enable` to re-enable them.
