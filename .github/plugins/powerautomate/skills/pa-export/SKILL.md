---
name: pa-export
description: >
  Export flow definitions from Dataverse to local JSON files.
  USE FOR: "export flow", "download flow", "clone flow", "backup flow",
  "get flow definition", "save flow locally", "inspect flow JSON".
  DO NOT USE FOR: importing flows (use pa-import),
  listing flows without downloading (use pa-list).
---

# Skill: Export — Download Flow Definitions to Local Files

Exports Power Automate cloud flow definitions from Dataverse to local JSON files. The exported files contain the full Logic Apps definition (`clientdata`) and can be edited locally and re-imported.

---

## Export a Single Flow

```bash
python scripts/export_flow.py --flow-id a1b2c3d4-e5f6-7890-abcd-ef1234567890 --dataverse-url https://org123.crm.dynamics.com
```

Or, if `DATAVERSE_URL` is set:

```bash
python scripts/export_flow.py --flow-id a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Don't know the flow ID?** Use `pa-list` first:

```bash
python scripts/list_flows.py
```

---

## Export All Flows

```bash
python scripts/export_flow.py --all --dataverse-url https://org123.crm.dynamics.com
```

Exports every category-5 flow in the environment. Each flow gets its own subdirectory.

---

## Output Structure

Each exported flow creates a directory under `workflows/`:

```
workflows/
  Handle-Customer-Request-a1b2c3d4/
    workflow.json      # The full clientdata — Logic Apps definition
    metadata.yml       # Flow metadata (name, ID, state, solution info)
```

### workflow.json

This is the flow's `clientdata` field from the Dataverse `workflow` entity — the complete Logic Apps JSON definition. It contains:

- **Triggers**: The event that starts the flow (e.g., `manual` trigger with `kind: "PowerApp"` for CPS flows)
- **Actions**: Every step in the flow (HTTP calls, conditions, compose, response, etc.)
- **Parameters**: Connection references, environment variables
- **Schema**: Input/output schemas for triggers and Response actions

This is the same JSON you'd see in the Power Automate portal's "Peek code" view.

### metadata.yml

Contains:

```yaml
name: Handle Customer Request
workflowid: a1b2c3d4-e5f6-7890-abcd-ef1234567890
statecode: 0
statuscode: 1
category: 5
resourcecontainerid: xxxx-xxxx
solutionid: yyyy-yyyy
```

---

## Editing Exported Flows

The exported `workflow.json` can be edited locally:

1. Open `workflow.json` in your editor
2. Modify triggers, actions, schemas as needed
3. Re-import with `pa-import`:

```bash
python scripts/import_flow.py --flow-json workflows/Handle-Customer-Request-a1b2c3d4/workflow.json --name "Handle Customer Request v2" --dataverse-url https://org123.crm.dynamics.com
```

### Common Edits

- **Add/remove actions**: Edit the `actions` object in the definition
- **Change trigger schema**: Edit `triggers.manual.inputs.schema` (for CPS input parameters)
- **Fix Response outputs**: Edit `actions.Response.inputs.body` and `actions.Response.inputs.schema`
- **Remove boolean outputs**: Change `"type": "boolean"` to `"type": "string"` in Response schema (see `pa-health` Gotcha 3)

---

## Use Cases

| Scenario | Command |
|----------|---------|
| Backup all flows before making changes | `python scripts/export_flow.py --all` |
| Inspect a specific flow's definition | `python scripts/export_flow.py --flow-id {id}` |
| Clone a flow to a new environment | Export → edit metadata → import with `pa-import` |
| Debug CPS integration issues | Export → inspect trigger kind, Response schema |
| Version control flows in Git | Export → commit `workflows/` directory |
