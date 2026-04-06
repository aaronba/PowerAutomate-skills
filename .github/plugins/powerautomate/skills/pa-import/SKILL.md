---
name: pa-import
description: >
  Import or create a Power Automate cloud flow from a JSON definition.
  USE FOR: "import flow", "create flow", "deploy flow", "upload flow",
  "restore flow", "push flow to environment".
  DO NOT USE FOR: exporting flows (use pa-export),
  enabling existing flows (use pa-enable).
---

# Skill: Import — Create or Deploy a Flow from JSON

Imports a Power Automate cloud flow from a local JSON definition into a Dataverse environment. Handles both the Dataverse record creation and Flow API runtime registration.

---

## The Two-Step Process

Importing a flow requires **two API calls** — this is the most important concept to understand:

### Step 1: Dataverse POST — Create the Workflow Record

```
POST /api/data/v9.2/workflows
```

Creates the `workflow` entity record with:
- `name`: Display name
- `category`: 5 (cloud flow)
- `clientdata`: The full Logic Apps JSON definition
- `type`: 1 (definition)

This gives the flow a Dataverse identity (workflowid) and solution membership, but it **cannot run yet**.

### Step 2: Flow API PATCH — Register the Runtime Definition

```
PATCH https://{flow-api-host}/providers/Microsoft.ProcessSimple/environments/{env-id}/flows/{flow-id}
```

Registers the flow definition with the Flow Management API runtime engine. This step:
- Makes the flow runnable
- Sets up trigger listeners
- Patches `kind: "Skills"` on triggers and Response actions (for CPS compatibility)

**Without Step 2, the flow exists in Dataverse but has no `resourcecontainerid` and cannot execute.**

---

## Basic Usage

```bash
python scripts/import_flow.py --flow-json workflows/Handle-Customer-Request/workflow.json --name "Handle Customer Request" --dataverse-url https://org123.crm.dynamics.com
```

Or, if `DATAVERSE_URL` is set:

```bash
python scripts/import_flow.py --flow-json workflows/Handle-Customer-Request/workflow.json --name "Handle Customer Request"
```

---

## Options

| Flag | Description |
|------|-------------|
| `--flow-json {path}` | Path to the workflow.json file (Logic Apps definition) |
| `--name {name}` | Display name for the flow |
| `--dataverse-url {url}` | Dataverse environment URL (or set `DATAVERSE_URL`) |
| `--solution {name}` | Add the flow to a specific solution |
| `--no-fix-kind` | Skip automatic kind:Skills patching |

---

## Adding to a Solution

If the flow should be part of a Dataverse solution (recommended for ALM):

```bash
python scripts/import_flow.py --flow-json workflow.json --name "My Flow" --solution MySolutionName
```

This uses the `MSCRM.SolutionName` header on the Dataverse POST to automatically add the flow as a solution component.

**IMPORTANT:** If you don't specify `--solution`, the flow is created in the default solution only and cannot be cleanly exported or deployed across environments.

---

## Automatic Behaviors

The import script automatically:

1. **Creates the Dataverse record** (POST to workflow entity)
2. **Registers with Flow API** (PATCH to flow definition endpoint)
3. **Patches kind:Skills** on triggers and Response actions (unless `--no-fix-kind`)
4. **Starts the flow** (activates the trigger)

After import, the flow is immediately enabled and ready to be invoked.

---

## kind:Skills — Why It Matters

For flows invoked by Copilot Studio, the `kind` property must be set correctly:

| Location | Required kind value | Purpose |
|----------|-------------------|---------|
| Trigger in Dataverse `clientdata` | `"PowerApp"` | Standard Logic Apps trigger type |
| Trigger in Flow API definition | `"Skills"` | Tells CPS this flow can be invoked as a skill |
| Response action in Dataverse `clientdata` | `"PowerApp"` | Standard Response type |
| Response action in Flow API definition | `"Skills"` | Enables CPS to read output mappings |

The import script sets these automatically. Use `--no-fix-kind` only if the flow is not meant for CPS integration.

---

## Example Workflows

### Import a previously exported flow

```bash
# Export from environment A
python scripts/export_flow.py --flow-id {id} --dataverse-url https://envA.crm.dynamics.com

# Import into environment B
python scripts/import_flow.py \
  --flow-json workflows/My-Flow-{id}/workflow.json \
  --name "My Flow" \
  --dataverse-url https://envB.crm.dynamics.com \
  --solution TargetSolution
```

### Create a new flow from a hand-crafted definition

```bash
python scripts/import_flow.py \
  --flow-json my-new-flow.json \
  --name "New Integration Flow" \
  --solution MySolution
```

### Import without CPS kind patching

```bash
python scripts/import_flow.py \
  --flow-json workflow.json \
  --name "Non-CPS Flow" \
  --no-fix-kind
```

---

## Troubleshooting

### "Flow created but not running"

The Dataverse record was created (Step 1) but Flow API registration (Step 2) failed. Check:
- Flow API auth is working (`pa-connect` Step 4)
- The environment ID in the Flow API URL matches the Dataverse environment
- Run `pa-health` to find flows with missing `resourcecontainerid`

### "Flow runs but CPS can't invoke it"

The `kind` property is likely missing or wrong. Run:

```bash
python scripts/enable_flow.py --fix-kind --flow-ids {id}
```

### "400 error on Dataverse POST"

Check that `workflow.json` is valid JSON and contains the expected Logic Apps definition structure (triggers, actions, etc.).
