# PowerAutomate-skills

Agent skills for managing Power Automate cloud flows — works with GitHub Copilot CLI and Claude Code.

## What's Included

- **7 skills** covering flow listing, export, import, editing, health checks, and enable/disable
- **Python scripts** using the official Microsoft Dataverse SDK + Flow Management REST API
- **GCC support** — works with both commercial and government cloud environments

## Prerequisites

- **Python 3.10+**
- **Microsoft Dataverse environment** with Power Automate flows
- Python packages:
  ```bash
  pip install azure-identity requests PowerPlatform-Dataverse-Client
  ```

## Getting Started

### GitHub Copilot CLI

```bash
copilot plugin install <path/to/PowerAutomate-skills>/.github/plugins/powerautomate
```

### Claude Code

```bash
claude --plugin-dir "<path/to/PowerAutomate-skills>/.github/plugins/powerautomate"
```

## Skills

| Skill | Description |
|-------|-------------|
| `pa-overview` | Routing and rules for all flow operations |
| `pa-connect` | Authenticate to Dataverse + Flow API |
| `pa-list` | List cloud flows in an environment |
| `pa-export` | Export flow definitions (workflow.json + metadata.yml) |
| `pa-import` | Create/import flows (two-step: Dataverse + Flow API) |
| `pa-health` | Health check: disabled flows, missing kind:Skills, boolean outputs |
| `pa-enable` | Enable/disable flows, patch kind:Skills for Copilot Studio |

## Architecture

Flow management requires **two APIs** working together:

1. **Dataverse Web API** — `workflow` entity (category=5), `clientdata` field stores flow JSON
2. **Flow Management API** — `api.flow.microsoft.com` — runtime registration, enable/disable, kind patching

Both APIs require separate authentication tokens.

## Cloud Endpoints

| API | Commercial | GCC |
|-----|-----------|-----|
| Dataverse | `*.crm.dynamics.com` | `*.crm9.dynamics.com` |
| Flow API | `api.flow.microsoft.com` | `gov.api.flow.microsoft.us` |

## License

[MIT](LICENSE)
