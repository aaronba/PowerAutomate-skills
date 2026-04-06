---
name: pa-connect
description: >
  Authenticate to Dataverse and Flow API for flow management.
  USE FOR: "connect to Flow API", "authenticate", "set up flow management",
  "configure PA", "first time setup", "test connection".
  DO NOT USE FOR: listing flows (use pa-list), enabling flows (use pa-enable).
---

# Skill: Connect — Authenticate for Flow Management

Sets up authentication for both the Dataverse Web API and Flow Management API. All flow management operations require tokens for both APIs.

---

## Step 1: Verify Python Packages

```bash
pip install --upgrade azure-identity requests PowerPlatform-Dataverse-Client
```

Verify installation:

```bash
python -c "from azure.identity import InteractiveBrowserCredential; print('azure-identity OK')"
python -c "import requests; print('requests OK')"
```

---

## Step 2: Set Environment Variables

Set these in `.env` at the repo root or as shell environment variables:

```env
DATAVERSE_URL=https://org123.crm.dynamics.com
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# Optional — override auto-detection
CPS_CLOUD=public
# Optional — for non-interactive (CI/CD) auth
CLIENT_ID=
CLIENT_SECRET=
```

**How to find your values:**
- `DATAVERSE_URL`: From the Power Platform Admin Center → Environments → your environment → Environment URL
- `TENANT_ID`: From Azure Portal → Azure Active Directory → Overview → Tenant ID, or from `pac org who` output
- `CPS_CLOUD`: Usually auto-detected from URL. Set explicitly only if detection fails.

---

## Step 3: Test Dataverse Authentication

```bash
python scripts/list_flows.py --dataverse-url https://org123.crm.dynamics.com
```

This tests Dataverse Web API auth by querying the `workflow` entity. On first run with interactive auth, a browser window opens for sign-in. The token is cached for subsequent calls.

**Expected output on success:**

```
Found N cloud flows:
  [enabled]  My Flow Name (workflow-id-guid)
  [disabled] Another Flow (workflow-id-guid)
```

If this fails, check:
- `DATAVERSE_URL` is correct and accessible
- `TENANT_ID` matches the environment's tenant
- Your account has the System Administrator or System Customizer role

---

## Step 4: Test Flow API Authentication

Flow API auth is tested automatically on first flow operation that needs it (enable, import, export definition). You can verify it explicitly:

```python
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from flow_auth import FlowAuth

auth = FlowAuth()
token = auth.get_flow_token()
print(f"Flow API token acquired (length: {len(token)})")
print(f"Flow API base: {auth.flow_api_base}")
```

The Flow API uses a different scope than Dataverse. Both tokens are acquired through the same credential but target different resources.

---

## Troubleshooting

### "AADSTS65001: The user or administrator has not consented"

The Flow API scope requires admin consent in some tenants. Options:
1. Ask a tenant admin to grant consent for the `https://service.flow.microsoft.com/.default` scope
2. Use a service principal with pre-granted permissions (`CLIENT_ID` + `CLIENT_SECRET`)

### "AADSTS50076: Due to a configuration change" (GCC/GCC-High)

GCC and GCC-High use different login authorities:
- GCC: `https://login.microsoftonline.com` (same as public)
- GCC-High: `https://login.microsoftonline.us`

If auto-detection fails, set `CPS_CLOUD=gcc` or `CPS_CLOUD=gcchigh` explicitly.

### "No module named 'flow_auth'"

Ensure you're running scripts from the repo root, or that `scripts/` is in your Python path:

```python
import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
from flow_auth import FlowAuth
```

### Token cache / expired token

Interactive tokens are cached by `azure-identity`. If you get auth errors after a long idle period, the cached token may have expired. Delete `.token_cache.bin` (if present) and re-authenticate.

---

## Connection Verification Checklist

After setup, verify both APIs work:

1. **Dataverse**: `python scripts/list_flows.py --dataverse-url {url}` returns flow list
2. **Flow API**: Any enable/import operation succeeds without auth errors
3. **Cloud detection**: Correct Flow API host is used (check script output)

Once both succeed, you're ready to use `pa-list`, `pa-export`, `pa-import`, `pa-health`, and `pa-enable`.
