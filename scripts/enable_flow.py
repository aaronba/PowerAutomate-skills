"""
enable_flow.py — Enable/disable flows and patch kind:Skills.

Usage:
    python enable_flow.py --enable --flow-ids <id1>,<id2>
    python enable_flow.py --enable                        # all disabled category-5 flows
    python enable_flow.py --disable --flow-ids <id>
    python enable_flow.py --fix-kind --flow-ids <id>
    python enable_flow.py --enable --fix-kind             # enable + patch all
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


def get_disabled_flow_ids(auth: FlowAuth, dv_token: str) -> list:
    """Return IDs of all disabled category-5 flows."""
    headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}
    url = (
        f"{auth.dataverse_url}/api/data/v9.2/workflows"
        f"?$filter=category eq 5 and statecode eq 1"
        f"&$select=workflowid,name"
    )
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return [w["workflowid"] for w in resp.json().get("value", [])]


def enable_flow(auth: FlowAuth, env_id: str, flow_id: str, flow_token: str) -> dict:
    url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}/start"
        f"?api-version=2016-11-01"
    )
    resp = requests.post(url, headers={"Authorization": f"Bearer {flow_token}"})
    resp.raise_for_status()
    return {"flowId": flow_id, "action": "enabled"}


def disable_flow(auth: FlowAuth, env_id: str, flow_id: str, flow_token: str) -> dict:
    url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}/stop"
        f"?api-version=2016-11-01"
    )
    resp = requests.post(url, headers={"Authorization": f"Bearer {flow_token}"})
    resp.raise_for_status()
    return {"flowId": flow_id, "action": "disabled"}


def fix_kind(auth: FlowAuth, env_id: str, flow_id: str, flow_token: str) -> dict:
    """Patch trigger + Response actions kind to 'Skills'."""
    flow_headers = {"Authorization": f"Bearer {flow_token}"}

    # Get current definition
    get_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}"
        f"?api-version=2016-11-01"
    )
    resp = requests.get(get_url, headers=flow_headers)
    resp.raise_for_status()
    definition = resp.json().get("properties", {}).get("definition", {})

    patched = False
    for trigger in definition.get("triggers", {}).values():
        if trigger.get("kind") != "Skills":
            trigger["kind"] = "Skills"
            patched = True

    for action in definition.get("actions", {}).values():
        if action.get("type", "").lower() == "response" and action.get("kind") != "Skills":
            action["kind"] = "Skills"
            patched = True

    if not patched:
        return {"flowId": flow_id, "action": "fix-kind", "result": "already correct"}

    patch_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}"
        f"?api-version=2016-11-01"
    )
    patch_body = {"properties": {"definition": definition}}
    patch_resp = requests.patch(
        patch_url,
        headers={**flow_headers, "Content-Type": "application/json"},
        json=patch_body,
    )
    patch_resp.raise_for_status()
    return {"flowId": flow_id, "action": "fix-kind", "result": "patched"}


def run(
    auth: FlowAuth,
    flow_ids: list = None,
    do_enable: bool = False,
    do_disable: bool = False,
    do_fix_kind: bool = False,
) -> dict:
    dv_token = auth.get_dataverse_token()
    flow_token = auth.get_flow_token()
    env_id = resolve_flow_env_id(auth, flow_token)

    # If no flow IDs specified and enabling, default to all disabled flows
    if not flow_ids and do_enable:
        flow_ids = get_disabled_flow_ids(auth, dv_token)

    if not flow_ids:
        return {"status": "ok", "message": "No flows to process", "results": []}

    results = []
    for fid in flow_ids:
        flow_result = {"flowId": fid, "actions": []}
        try:
            if do_enable:
                r = enable_flow(auth, env_id, fid, flow_token)
                flow_result["actions"].append(r)
            if do_disable:
                r = disable_flow(auth, env_id, fid, flow_token)
                flow_result["actions"].append(r)
            if do_fix_kind:
                r = fix_kind(auth, env_id, fid, flow_token)
                flow_result["actions"].append(r)
        except Exception as e:
            flow_result["error"] = str(e)
        results.append(flow_result)

    return {"status": "ok", "count": len(results), "results": results}


def main():
    parser = argparse.ArgumentParser(description="Enable/disable flows and patch kind")
    parser.add_argument(
        "--flow-ids",
        help="Comma-separated flow IDs (omit for all disabled category-5 flows)",
    )
    parser.add_argument("--enable", action="store_true", help="Start flows")
    parser.add_argument("--disable", action="store_true", help="Stop flows")
    parser.add_argument("--fix-kind", action="store_true", help="Patch kind to Skills")
    parser.add_argument("--dataverse-url", default=os.environ.get("DATAVERSE_URL"))
    parser.add_argument("--cloud", default=os.environ.get("CPS_CLOUD"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID"))
    args = parser.parse_args()

    if not args.enable and not args.disable and not args.fix_kind:
        parser.error("Specify at least one action: --enable, --disable, or --fix-kind")

    flow_ids = [fid.strip() for fid in args.flow_ids.split(",")] if args.flow_ids else None

    try:
        auth = FlowAuth(
            dataverse_url=args.dataverse_url,
            cloud=args.cloud,
            tenant_id=args.tenant_id,
        )
        result = run(
            auth,
            flow_ids=flow_ids,
            do_enable=args.enable,
            do_disable=args.disable,
            do_fix_kind=args.fix_kind,
        )
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
