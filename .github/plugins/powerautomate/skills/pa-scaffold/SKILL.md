---
name: pa-scaffold
description: >
  Generate a complete Power Automate cloud flow definition from a natural language
  description. Produces a valid workflow.json ready for import via pa-import.
  USE FOR: "create a flow that", "scaffold a flow", "generate a flow",
  "build a flow", "new flow that does", "make a flow for",
  "I need a flow that", "design a flow".
  DO NOT USE FOR: importing existing JSON (use pa-import),
  exporting flows (use pa-export), editing existing flows in the portal.
---

# Skill: Scaffold — AI-Driven Flow Generation

Generate a complete, valid Power Automate cloud flow definition from a natural language description. The output is a `workflow.json` file ready for deployment via `pa-import`.

---

## How It Works

1. User describes what the flow should do in plain language
2. You generate a valid Logic Apps workflow definition JSON
3. Save it as `workflow.json`
4. User deploys it with `pa-import`

---

## Hard Rules — Read Before Generating

### 1. Output Format

Every generated flow MUST produce a file with this exact top-level structure:

```json
{
  "properties": {
    "connectionReferences": {},
    "definition": {
      "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
      "contentVersion": "1.0.0.0",
      "parameters": {
        "$connections": { "defaultValue": {}, "type": "Object" },
        "$authentication": { "defaultValue": {}, "type": "SecureObject" }
      },
      "triggers": { ... },
      "actions": { ... },
      "outputs": {}
    }
  },
  "schemaVersion": "1.0.0.0"
}
```

**NEVER** omit `$schema`, `contentVersion`, `schemaVersion`, or `parameters`. The Flow API rejects definitions missing these fields.

### 2. Trigger — Always `manual` with `kind: "Skills"`

Every CPS-callable flow uses a manual Request trigger:

```json
"triggers": {
  "manual": {
    "type": "Request",
    "kind": "Skills",
    "inputs": {
      "schema": {
        "type": "object",
        "properties": {
          "inputName": {
            "title": "Input Display Name",
            "description": "What this input is for",
            "type": "string",
            "x-ms-content-hint": "TEXT",
            "x-ms-dynamically-added": true
          }
        },
        "required": ["inputName"]
      }
    }
  }
}
```

**Rules:**
- Trigger name MUST be `"manual"`
- `kind` MUST be `"Skills"` (not `"PowerApp"`, not `"VirtualAgent"`)
- Every input property MUST have `title`, `description`, `type`, `x-ms-content-hint`, and `x-ms-dynamically-added: true`
- Supported input types: `"string"`, `"number"`, `"integer"` — **NEVER** use `"boolean"` (breaks CPS)
- `x-ms-content-hint` values: `"TEXT"` for strings, `"NUMBER"` for numbers

### 3. Response — Always `kind: "Skills"`

Every flow must end with a Response action:

```json
"Respond_to_the_agent": {
  "type": "Response",
  "kind": "Skills",
  "inputs": {
    "statusCode": 200,
    "schema": {
      "type": "object",
      "properties": {
        "outputName": {
          "title": "Output Display Name",
          "description": "What this output contains",
          "type": "string",
          "x-ms-content-hint": "TEXT",
          "x-ms-dynamically-added": true
        }
      },
      "additionalProperties": {}
    },
    "body": {
      "outputName": "@{actions('SomeAction').outputs.body.value}"
    }
  },
  "runAfter": {
    "LastAction": ["SUCCEEDED"]
  }
}
```

**Rules:**
- `kind` MUST be `"Skills"`
- `statusCode` MUST be `200`
- **NEVER** use `"type": "boolean"` in output properties — breaks ALL CPS output mappings
- `body` must reference actual action outputs using Logic Apps expressions
- Include `"additionalProperties": {}` in the schema

### 4. Boolean Ban

**NEVER** use `"type": "boolean"` anywhere in trigger input schemas or Response output schemas. This breaks Copilot Studio output mappings silently.

Instead use:
- `"type": "string"` with values `"true"` / `"false"`
- `"type": "integer"` with values `1` / `0`

### 5. Action runAfter Chains

Actions execute based on `runAfter` dependencies, not order in JSON:

```json
"actions": {
  "Step_1": {
    "type": "...",
    "inputs": { ... },
    "runAfter": {}
  },
  "Step_2": {
    "type": "...",
    "inputs": { ... },
    "runAfter": { "Step_1": ["SUCCEEDED"] }
  },
  "Respond_to_the_agent": {
    "type": "Response",
    "kind": "Skills",
    "inputs": { ... },
    "runAfter": { "Step_2": ["SUCCEEDED"] }
  }
}
```

- First action: `"runAfter": {}`
- Each subsequent action: `"runAfter": { "PreviousAction": ["SUCCEEDED"] }`
- Response is always last in the chain
- Action names use underscores, not spaces: `"Get_Customer_Data"`, not `"Get Customer Data"`

### 6. Referencing Trigger Inputs in Expressions

To reference a trigger input value:
```
@triggerBody()?['inputPropertyName']
```

String interpolation:
```
@{triggerBody()?['inputPropertyName']}
```

### 7. Referencing Action Outputs in Expressions

To reference a previous action's output:
```
@actions('ActionName').outputs.body
@actions('ActionName').outputs.body.value
@{actions('ActionName').outputs.body?['propertyName']}
```

For Dataverse List Records results:
```
@{first(outputs('List_rows')?['body/value'])?['fieldname']}
@{length(outputs('List_rows')?['body/value'])}
```

---

## Supported Action Types

### Compose — Transform or construct data

```json
"Build_Message": {
  "type": "Compose",
  "inputs": "Hello @{triggerBody()?['name']}, your request has been received.",
  "runAfter": {}
}
```

Reference output: `@outputs('Build_Message')`

### HTTP — Call an external API

```json
"Call_API": {
  "type": "Http",
  "inputs": {
    "method": "GET",
    "uri": "https://api.example.com/data/@{triggerBody()?['id']}",
    "headers": {
      "Content-Type": "application/json"
    }
  },
  "runAfter": {}
}
```

Reference output: `@body('Call_API')?['result']`

### Dataverse — List Records

```json
"List_rows": {
  "type": "OpenApiConnection",
  "inputs": {
    "parameters": {
      "entityName": "contacts",
      "$filter": "emailaddress1 eq '@{triggerBody()?['email']}'",
      "$select": "fullname,emailaddress1,telephone1",
      "$top": 1
    },
    "host": {
      "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
      "operationId": "ListRecords",
      "connectionName": "shared_commondataserviceforapps"
    }
  },
  "runAfter": {}
}
```

When using Dataverse, add a connectionReference:
```json
"connectionReferences": {
  "shared_commondataserviceforapps": {
    "api": { "name": "shared_commondataserviceforapps" },
    "connection": {
      "connectionReferenceLogicalName": "yourprefix_sharedcommondataserviceforapps_ref"
    },
    "runtimeSource": "embedded"
  }
}
```

**IMPORTANT:** The `connectionReferenceLogicalName` is environment-specific. Use a placeholder like `"yourprefix_sharedcommondataserviceforapps_ref"` — the user must update this after import or create the connection reference in their environment.

### Dataverse — Get Row

```json
"Get_record": {
  "type": "OpenApiConnection",
  "inputs": {
    "parameters": {
      "entityName": "accounts",
      "recordId": "@triggerBody()?['accountId']",
      "$select": "name,revenue,address1_city"
    },
    "host": {
      "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
      "operationId": "GetItem",
      "connectionName": "shared_commondataserviceforapps"
    }
  },
  "runAfter": {}
}
```

### Dataverse — Create Row

```json
"Create_record": {
  "type": "OpenApiConnection",
  "inputs": {
    "parameters": {
      "entityName": "tasks",
      "item": {
        "subject": "@triggerBody()?['taskName']",
        "description": "@triggerBody()?['description']"
      }
    },
    "host": {
      "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
      "operationId": "CreateRecord",
      "connectionName": "shared_commondataserviceforapps"
    }
  },
  "runAfter": {}
}
```

### Condition (If/Then/Else)

```json
"Check_Result": {
  "type": "If",
  "expression": {
    "and": [
      {
        "greater": [
          "@length(outputs('List_rows')?['body/value'])",
          0
        ]
      }
    ]
  },
  "actions": {
    "Found_Result": {
      "type": "Compose",
      "inputs": "@first(outputs('List_rows')?['body/value'])"
    }
  },
  "else": {
    "actions": {
      "No_Result": {
        "type": "Compose",
        "inputs": "No records found"
      }
    }
  },
  "runAfter": { "List_rows": ["SUCCEEDED"] }
}
```

### For Each — Loop over an array

```json
"Process_Each_Record": {
  "type": "Foreach",
  "foreach": "@outputs('List_rows')?['body/value']",
  "actions": {
    "Process_Record": {
      "type": "Compose",
      "inputs": "@items('Process_Each_Record')?['fullname']"
    }
  },
  "runAfter": { "List_rows": ["SUCCEEDED"] }
}
```

### Parse JSON — Extract structured data

```json
"Parse_Response": {
  "type": "ParseJson",
  "inputs": {
    "content": "@body('Call_API')",
    "schema": {
      "type": "object",
      "properties": {
        "name": { "type": "string" },
        "score": { "type": "number" }
      }
    }
  },
  "runAfter": { "Call_API": ["SUCCEEDED"] }
}
```

Reference output: `@body('Parse_Response')?['name']`

---

## Complete Example — Customer Lookup Flow

User says: *"Create a flow that takes a customer email, looks them up in Dataverse contacts, and returns their name and phone number"*

Generated `workflow.json`:

```json
{
  "properties": {
    "connectionReferences": {
      "shared_commondataserviceforapps": {
        "api": { "name": "shared_commondataserviceforapps" },
        "connection": {
          "connectionReferenceLogicalName": "yourprefix_sharedcommondataserviceforapps_ref"
        },
        "runtimeSource": "embedded"
      }
    },
    "definition": {
      "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
      "contentVersion": "1.0.0.0",
      "parameters": {
        "$connections": { "defaultValue": {}, "type": "Object" },
        "$authentication": { "defaultValue": {}, "type": "SecureObject" }
      },
      "triggers": {
        "manual": {
          "type": "Request",
          "kind": "Skills",
          "inputs": {
            "schema": {
              "type": "object",
              "properties": {
                "email": {
                  "title": "Customer Email",
                  "description": "Email address to look up",
                  "type": "string",
                  "x-ms-content-hint": "TEXT",
                  "x-ms-dynamically-added": true
                }
              },
              "required": ["email"]
            }
          }
        }
      },
      "actions": {
        "Find_Contact": {
          "type": "OpenApiConnection",
          "inputs": {
            "parameters": {
              "entityName": "contacts",
              "$filter": "emailaddress1 eq '@{triggerBody()?['email']}'",
              "$select": "fullname,telephone1",
              "$top": 1
            },
            "host": {
              "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
              "operationId": "ListRecords",
              "connectionName": "shared_commondataserviceforapps"
            }
          },
          "runAfter": {}
        },
        "Check_Found": {
          "type": "If",
          "expression": {
            "and": [
              {
                "greater": [
                  "@length(outputs('Find_Contact')?['body/value'])",
                  0
                ]
              }
            ]
          },
          "actions": {
            "Build_Found_Response": {
              "type": "Compose",
              "inputs": {
                "customerName": "@{first(outputs('Find_Contact')?['body/value'])?['fullname']}",
                "phone": "@{first(outputs('Find_Contact')?['body/value'])?['telephone1']}",
                "found": "true"
              }
            }
          },
          "else": {
            "actions": {
              "Build_NotFound_Response": {
                "type": "Compose",
                "inputs": {
                  "customerName": "",
                  "phone": "",
                  "found": "false"
                }
              }
            }
          },
          "runAfter": { "Find_Contact": ["SUCCEEDED"] }
        },
        "Respond_to_the_agent": {
          "type": "Response",
          "kind": "Skills",
          "inputs": {
            "statusCode": 200,
            "schema": {
              "type": "object",
              "properties": {
                "customerName": {
                  "title": "Customer Name",
                  "description": "Full name of the customer",
                  "type": "string",
                  "x-ms-content-hint": "TEXT",
                  "x-ms-dynamically-added": true
                },
                "phone": {
                  "title": "Phone Number",
                  "description": "Customer phone number",
                  "type": "string",
                  "x-ms-content-hint": "TEXT",
                  "x-ms-dynamically-added": true
                },
                "found": {
                  "title": "Found",
                  "description": "Whether a matching contact was found (true/false)",
                  "type": "string",
                  "x-ms-content-hint": "TEXT",
                  "x-ms-dynamically-added": true
                }
              },
              "additionalProperties": {}
            },
            "body": {
              "customerName": "@{if(greater(length(outputs('Find_Contact')?['body/value']),0),first(outputs('Find_Contact')?['body/value'])?['fullname'],'')}",
              "phone": "@{if(greater(length(outputs('Find_Contact')?['body/value']),0),first(outputs('Find_Contact')?['body/value'])?['telephone1'],'')}",
              "found": "@{if(greater(length(outputs('Find_Contact')?['body/value']),0),'true','false')}"
            }
          },
          "runAfter": { "Check_Found": ["SUCCEEDED"] }
        }
      },
      "outputs": {}
    }
  },
  "schemaVersion": "1.0.0.0"
}
```

---

## Workflow After Generation

1. **Generate**: You produce the `workflow.json` based on the user's description
2. **Review**: User reviews the generated definition
3. **Save**: Write to `workflows/{flow-name}/workflow.json`
4. **Deploy**: User runs `pa-import` to create the flow in their environment:
   ```bash
   python scripts/import_flow.py \
     --flow-json workflows/{flow-name}/workflow.json \
     --name "Flow Display Name" \
     --dataverse-url https://orgXXX.crm.dynamics.com
   ```
5. **Verify**: User runs `pa-health` to confirm the flow is healthy

---

## Common Patterns

### Echo / Passthrough
Takes input, returns it directly. Good for testing CPS-to-flow connectivity.

### Dataverse Lookup
Takes an identifier, queries Dataverse, returns fields from the matched record.

### Multi-Step Pipeline
Chains multiple actions: fetch data → transform → call external API → return result.

### HTTP Integration
Calls an external REST API and returns parsed results to CPS.

### Conditional Routing
Uses If/Then/Else to return different responses based on data conditions.

---

## Checklist Before Saving

Before writing the generated `workflow.json`, verify:

- [ ] Top-level structure: `properties.definition` + `schemaVersion`
- [ ] `$schema` and `contentVersion` present in definition
- [ ] `$connections` and `$authentication` in parameters
- [ ] Trigger is `"manual"` with `kind: "Skills"`
- [ ] All trigger inputs have `title`, `description`, `type`, `x-ms-content-hint`
- [ ] Response has `kind: "Skills"` and `statusCode: 200`
- [ ] **No boolean types** in trigger inputs or Response outputs
- [ ] All `runAfter` chains are correct (first action = `{}`, each subsequent references predecessor)
- [ ] Response `body` expressions reference actual action outputs
- [ ] `connectionReferences` included if using Dataverse or other connectors
- [ ] Action names use underscores, not spaces
