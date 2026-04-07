"""
health_check.py — Classify and health-check Power Automate cloud flows.

Classifies every category-5 flow into one of four categories based on its
trigger, then runs the appropriate checks for each:

  cps-skills    — CPS-callable flow (trigger kind == "Skills")
                  Checks: enabled, resourcecontainer, kind:Skills on
                  trigger + Response actions, no boolean outputs.
  cps-legacy    — Older CPS flow (trigger kind == "VirtualAgent")
                  Checks: enabled, resourcecontainer. Flagged as upgradeable.
  platform      — System flow (Recurrence, Dataverse triggers, etc.)
                  Checks: enabled only.
  unknown       — Could not fetch definition to classify.
                  Checks: enabled only.

Usage:
    python health_check.py --dataverse-url https://org123.crm9.dynamics.com
    python health_check.py --fix              # auto-remediate CPS flows
    python health_check.py --flow-ids <id>... # check specific flows
"""

import argparse
import json
import os
import sys

import requests
from flow_auth import FlowAuth

DV_HEADERS = {
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}

# Trigger types that indicate a CPS-callable flow
CPS_TRIGGER_KINDS = {"Skills", "VirtualAgent"}

# Trigger types that indicate a platform/system flow
PLATFORM_TRIGGER_TYPES = {"Recurrence", "ApiConnectionNotification"}


def resolve_flow_env_id(auth: FlowAuth, flow_token: str) -> str:
    url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments?api-version=2016-11-01"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {flow_token}"},
                        timeout=30)
    resp.raise_for_status()

    target = auth.dataverse_url.rstrip("/").lower()
    for env in resp.json().get("value", []):
        instance_url = (
            env.get("properties", {})
            .get("linkedEnvironmentMetadata", {})
            .get("instanceUrl", "")
            .rstrip("/")
            .lower()
        )
        if instance_url == target:
            return env["name"]

    raise ValueError(
        f"No Flow API environment found matching Dataverse URL: {auth.dataverse_url}"
    )


def classify_flow(triggers: dict) -> str:
    """Classify a flow based on its trigger kind and type."""
    for trigger in triggers.values():
        kind = trigger.get("kind")
        ttype = trigger.get("type", "")
        if kind == "Skills":
            return "cps-skills"
        if kind == "VirtualAgent":
            return "cps-legacy"
        if ttype in PLATFORM_TRIGGER_TYPES:
            return "platform"
    return "platform"


def check_boolean_outputs(actions: dict) -> list:
    """Find Response actions with boolean-typed outputs in their schema."""
    issues = []
    for name, action in actions.items():
        if action.get("type", "").lower() != "response":
            continue
        schema = action.get("inputs", {}).get("schema", {})
        properties = schema.get("properties", {})
        for prop_name, prop_def in properties.items():
            if prop_def.get("type") == "boolean":
                issues.append(
                    f"Response '{name}' has boolean output '{prop_name}' — "
                    f"breaks CPS output mappings"
                )
    return issues


def enable_flow_fix(auth, env_id, flow_id, flow_token):
    """Enable a flow via Flow API + Dataverse statecode sync."""
    start_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}/start"
        f"?api-version=2016-11-01"
    )
    requests.post(
        start_url, headers={"Authorization": f"Bearer {flow_token}"},
        timeout=30,
    ).raise_for_status()

    dv_token = auth.get_dataverse_token()
    requests.patch(
        f"{auth.dataverse_url}/api/data/v9.2/workflows({flow_id})",
        headers={
            **DV_HEADERS,
            "Authorization": f"Bearer {dv_token}",
            "Content-Type": "application/json",
        },
        json={"statecode": 0, "statuscode": 1},
        timeout=30,
    ).raise_for_status()


def patch_kind_skills(auth, env_id, flow_id, flow_token, definition):
    """Patch trigger + Response action kind to 'Skills' via Flow API."""
    for trigger in definition.get("triggers", {}).values():
        trigger["kind"] = "Skills"
    for action in definition.get("actions", {}).values():
        if action.get("type", "").lower() == "response":
            action["kind"] = "Skills"

    patch_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}"
        f"?api-version=2016-11-01"
    )
    requests.patch(
        patch_url,
        headers={
            "Authorization": f"Bearer {flow_token}",
            "Content-Type": "application/json",
        },
        json={"properties": {"definition": definition}},
        timeout=30,
    ).raise_for_status()


def fetch_flow_definition(auth, env_id, flow_id, flow_token):
    """Fetch a flow's definition from the Flow API. Returns (definition, error)."""
    flow_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}"
        f"?api-version=2016-11-01"
    )
    try:
        resp = requests.get(
            flow_url, headers={"Authorization": f"Bearer {flow_token}"},
            timeout=30,
        )
        if resp.ok:
            return resp.json().get("properties", {}).get("definition", {}), None
        return None, f"HTTP {resp.status_code}"
    except Exception as e:
        return None, str(e)


def check_flow(auth, workflow, env_id, flow_token, fix=False, enable_all=False):
    """Check a single flow: classify it, then run category-appropriate checks."""
    flow_id = workflow["workflowid"]
    flow_name = workflow.get("name", "unknown")
    issues = []
    fixes_applied = []

    # All categories: check enabled
    disabled = workflow.get("statecode") != 0
    if disabled:
        issues.append("Disabled (statecode != 0)")

    # Fetch definition for classification and deeper checks
    definition, fetch_err = fetch_flow_definition(auth, env_id, flow_id, flow_token)

    if definition:
        triggers = definition.get("triggers", {})
        actions = definition.get("actions", {})
        category = classify_flow(triggers)
    else:
        category = "unknown"
        if fetch_err:
            issues.append(f"Could not fetch definition: {fetch_err}")

    # Category-specific checks
    if category in ("cps-skills", "cps-legacy"):
        # CPS flows need resourcecontainer
        if not workflow.get("resourcecontainer"):
            issues.append("Missing resourcecontainer — not registered with Flow API")

        if category == "cps-legacy":
            issues.append("Uses kind:VirtualAgent — upgradeable to kind:Skills")

    if category == "cps-skills" and definition:
        # Check kind:Skills on trigger + Response actions
        needs_kind_patch = False
        for tname, trigger in triggers.items():
            if trigger.get("kind") != "Skills":
                issues.append(f"Trigger '{tname}' kind is '{trigger.get('kind')}'")
                needs_kind_patch = True
        for aname, action in actions.items():
            if action.get("type", "").lower() == "response":
                if action.get("kind") != "Skills":
                    issues.append(f"Response '{aname}' kind is '{action.get('kind')}'")
                    needs_kind_patch = True

        # Boolean output check
        issues.extend(check_boolean_outputs(actions))

        # Fix kind if requested
        if fix and needs_kind_patch:
            try:
                patch_kind_skills(auth, env_id, flow_id, flow_token, definition)
                fixes_applied.append("Patched kind:Skills on trigger + Response actions")
            except Exception as e:
                issues.append(f"Fix failed — could not patch kind: {e}")

    # Enable disabled flows: --enable-all for any flow, --fix for CPS only
    if disabled and (enable_all or (fix and category in ("cps-skills", "cps-legacy"))):
        try:
            enable_flow_fix(auth, env_id, flow_id, flow_token)
            fixes_applied.append("Enabled flow via Flow API + Dataverse")
        except Exception as e:
            issues.append(f"Fix failed — could not enable: {e}")

    result = {
        "flowId": flow_id,
        "name": flow_name,
        "category": category,
        "statecode": workflow.get("statecode"),
        "issues": issues,
        "healthy": len(issues) == 0,
    }
    if fixes_applied:
        result["fixesApplied"] = fixes_applied
    return result


def health_check(auth, fix=False, enable_all=False, flow_ids=None, verbose=False):
    dv_token = auth.get_dataverse_token()
    flow_token = auth.get_flow_token()
    dv_headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}

    url = (
        f"{auth.dataverse_url}/api/data/v9.2/workflows"
        f"?$filter=category eq 5"
        f"&$select=workflowid,name,statecode,statuscode,resourcecontainer"
    )
    resp = requests.get(url, headers=dv_headers, timeout=30)
    resp.raise_for_status()
    workflows = resp.json().get("value", [])

    if flow_ids:
        id_set = set(fid.lower() for fid in flow_ids)
        workflows = [wf for wf in workflows if wf["workflowid"].lower() in id_set]

    env_id = resolve_flow_env_id(auth, flow_token)

    total = len(workflows)
    if verbose:
        print(f"Checking {total} flows in env {env_id}...", file=sys.stderr, flush=True)

    results = []
    for i, wf in enumerate(workflows):
        if verbose:
            print(f"  [{i+1}/{total}] {wf.get('name', '?')}...", file=sys.stderr, flush=True)
        result = check_flow(auth, wf, env_id, flow_token, fix=fix, enable_all=enable_all)
        results.append(result)

    # Build summary by category
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "healthy": 0, "unhealthy": 0}
        categories[cat]["total"] += 1
        if r["healthy"]:
            categories[cat]["healthy"] += 1
        else:
            categories[cat]["unhealthy"] += 1

    healthy_count = sum(1 for r in results if r["healthy"])
    return {
        "status": "ok",
        "total": len(results),
        "healthy": healthy_count,
        "unhealthy": len(results) - healthy_count,
        "categories": categories,
        "flows": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Health check for Power Automate flows")
    parser.add_argument("--dataverse-url", default=os.environ.get("DATAVERSE_URL"))
    parser.add_argument("--cloud", default=os.environ.get("CPS_CLOUD"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID"))
    parser.add_argument("--fix", action="store_true", help="Auto-remediate CPS flow issues (kind, enable)")
    parser.add_argument("--enable-all", action="store_true", help="Enable all disabled flows regardless of category")
    parser.add_argument("--flow-ids", nargs="+", help="Check only specific flow IDs")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress")
    args = parser.parse_args()

    try:
        auth = FlowAuth(
            dataverse_url=args.dataverse_url,
            cloud=args.cloud,
            tenant_id=args.tenant_id,
        )
        result = health_check(auth, fix=args.fix, enable_all=args.enable_all,
                              flow_ids=args.flow_ids, verbose=args.verbose)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
