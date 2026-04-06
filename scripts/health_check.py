"""
health_check.py — Comprehensive health check for Power Automate cloud flows.

Checks each category-5 flow for:
  1. Is it enabled? (statecode == 0)
  2. Has resourcecontainer? (registered with Flow API)
  3. Trigger kind == "Skills"
  4. All Response actions have kind == "Skills"
  5. No boolean outputs in Response schemas (breaks CPS output mappings)

Usage:
    python health_check.py --dataverse-url https://org123.crm9.dynamics.com
    python health_check.py --fix   # auto-remediate issues
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


def resolve_flow_env_id(auth: FlowAuth, flow_token: str) -> str:
    url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments?api-version=2016-11-01"
    )
    resp = requests.get(url, headers={"Authorization": f"Bearer {flow_token}"})
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


def check_flow(
    auth: FlowAuth,
    workflow: dict,
    env_id: str,
    flow_token: str,
    fix: bool = False,
) -> dict:
    flow_id = workflow["workflowid"]
    flow_name = workflow.get("name", "unknown")
    issues = []
    fixes_applied = []

    # Check 1: Enabled?
    if workflow.get("statecode") != 0:
        issues.append("Flow is disabled (statecode != 0)")
        if fix:
            try:
                start_url = (
                    f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
                    f"/environments/{env_id}/flows/{flow_id}/start"
                    f"?api-version=2016-11-01"
                )
                resp = requests.post(
                    start_url, headers={"Authorization": f"Bearer {flow_token}"}
                )
                resp.raise_for_status()
                fixes_applied.append("Enabled flow via Flow API")
            except Exception as e:
                issues.append(f"Fix failed — could not enable: {e}")

    # Check 2: Has resourcecontainer?
    has_resource = bool(workflow.get("resourcecontainer"))
    if not has_resource:
        issues.append("Missing resourcecontainer — not registered with Flow API")

    # Checks 3-5: Get definition from Flow API
    definition = None
    try:
        flow_url = (
            f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
            f"/environments/{env_id}/flows/{flow_id}"
            f"?api-version=2016-11-01"
        )
        flow_resp = requests.get(
            flow_url, headers={"Authorization": f"Bearer {flow_token}"}
        )
        if flow_resp.ok:
            flow_data = flow_resp.json()
            definition = flow_data.get("properties", {}).get("definition", {})
        else:
            issues.append(
                f"Could not fetch Flow API definition (HTTP {flow_resp.status_code})"
            )
    except Exception as e:
        issues.append(f"Error fetching Flow API definition: {e}")

    needs_kind_patch = False

    if definition:
        triggers = definition.get("triggers", {})
        actions = definition.get("actions", {})

        # Check 3: Trigger kind
        for tname, trigger in triggers.items():
            if trigger.get("kind") != "Skills":
                issues.append(f"Trigger '{tname}' kind is '{trigger.get('kind')}', expected 'Skills'")
                needs_kind_patch = True

        # Check 4: Response action kind
        for aname, action in actions.items():
            if action.get("type", "").lower() == "response":
                if action.get("kind") != "Skills":
                    issues.append(
                        f"Response '{aname}' kind is '{action.get('kind')}', expected 'Skills'"
                    )
                    needs_kind_patch = True

        # Check 5: Boolean outputs
        bool_issues = check_boolean_outputs(actions)
        issues.extend(bool_issues)

        # Auto-fix kind if requested
        if fix and needs_kind_patch:
            try:
                for trigger in triggers.values():
                    trigger["kind"] = "Skills"
                for action in actions.values():
                    if action.get("type", "").lower() == "response":
                        action["kind"] = "Skills"

                patch_url = (
                    f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
                    f"/environments/{env_id}/flows/{flow_id}"
                    f"?api-version=2016-11-01"
                )
                patch_body = {"properties": {"definition": definition}}
                patch_resp = requests.patch(
                    patch_url,
                    headers={
                        "Authorization": f"Bearer {flow_token}",
                        "Content-Type": "application/json",
                    },
                    json=patch_body,
                )
                patch_resp.raise_for_status()
                fixes_applied.append("Patched kind:Skills on trigger + Response actions")
            except Exception as e:
                issues.append(f"Fix failed — could not patch kind: {e}")

    result = {
        "flowId": flow_id,
        "name": flow_name,
        "statecode": workflow.get("statecode"),
        "issues": issues,
        "healthy": len(issues) == 0,
    }
    if fixes_applied:
        result["fixesApplied"] = fixes_applied
    return result


def health_check(auth: FlowAuth, fix: bool = False) -> dict:
    dv_token = auth.get_dataverse_token()
    flow_token = auth.get_flow_token()

    dv_headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}

    # Get all category-5 flows (include disabled for health check)
    url = (
        f"{auth.dataverse_url}/api/data/v9.2/workflows"
        f"?$filter=category eq 5"
        f"&$select=workflowid,name,statecode,statuscode,resourcecontainer"
    )
    resp = requests.get(url, headers=dv_headers)
    resp.raise_for_status()
    workflows = resp.json().get("value", [])

    env_id = resolve_flow_env_id(auth, flow_token)

    results = []
    for wf in workflows:
        result = check_flow(auth, wf, env_id, flow_token, fix=fix)
        results.append(result)

    healthy_count = sum(1 for r in results if r["healthy"])
    return {
        "status": "ok",
        "total": len(results),
        "healthy": healthy_count,
        "unhealthy": len(results) - healthy_count,
        "flows": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Health check for Power Automate flows")
    parser.add_argument("--dataverse-url", default=os.environ.get("DATAVERSE_URL"))
    parser.add_argument("--cloud", default=os.environ.get("CPS_CLOUD"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID"))
    parser.add_argument("--fix", action="store_true", help="Auto-remediate issues")
    args = parser.parse_args()

    try:
        auth = FlowAuth(
            dataverse_url=args.dataverse_url,
            cloud=args.cloud,
            tenant_id=args.tenant_id,
        )
        result = health_check(auth, fix=args.fix)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
