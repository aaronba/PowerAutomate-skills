"""
import_flow.py — Import/create a Power Automate flow via Dataverse + Flow API.

Steps:
  1. POST workflow record to Dataverse (creates the flow entity)
  2. PATCH definition to Flow API (syncs the definition to the runtime)
  3. Optionally patch kind:Skills on trigger + Response actions
  4. Start the flow via Flow API

Usage:
    python import_flow.py --flow-json ./workflows/my-flow/workflow.json --name "My Flow"
    python import_flow.py --flow-json workflow.json --name "My Flow" --solution MySolution
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
    "Content-Type": "application/json",
}


def resolve_flow_env_id(auth: FlowAuth, flow_token: str) -> str:
    """Resolve the Flow API environment ID that matches the Dataverse URL."""
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


def patch_kind_skills(definition: dict) -> dict:
    """Set kind='Skills' on the trigger and all Response actions."""
    if "triggers" in definition:
        for trigger in definition["triggers"].values():
            trigger["kind"] = "Skills"

    if "actions" in definition:
        for action in definition["actions"].values():
            if action.get("type", "").lower() == "response":
                action["kind"] = "Skills"

    return definition


def import_flow(
    auth: FlowAuth,
    flow_json_path: str,
    name: str,
    solution: str = None,
    fix_kind: bool = True,
) -> dict:
    with open(flow_json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Normalize: clientdata must have properties.definition envelope
    if "properties" in raw and "definition" in raw["properties"]:
        clientdata = raw
        definition = raw["properties"]["definition"]
    else:
        # Bare definition — wrap it in the required envelope
        definition = raw
        clientdata = {
            "properties": {
                "connectionReferences": {},
                "definition": definition,
            },
            "schemaVersion": "1.0.0.0",
        }

    dv_token = auth.get_dataverse_token()
    flow_token = auth.get_flow_token()

    # Step 1: Create workflow record in Dataverse
    dv_headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}
    if solution:
        dv_headers["MSCRM.SolutionUniqueName"] = solution

    payload = {
        "name": name,
        "category": 5,
        "type": 1,
        "primaryentity": "none",
        "clientdata": json.dumps(clientdata),
    }
    create_url = f"{auth.dataverse_url}/api/data/v9.2/workflows"
    resp = requests.post(create_url, headers=dv_headers, json=payload)
    resp.raise_for_status()

    # Extract flow ID from OData-EntityId header
    entity_id_header = resp.headers.get("OData-EntityId", "")
    flow_id = entity_id_header.split("(")[-1].rstrip(")")
    if not flow_id or len(flow_id) < 30:
        raise ValueError(f"Could not extract flow ID from response: {entity_id_header}")

    # Step 2: Patch definition to Flow API
    env_id = resolve_flow_env_id(auth, flow_token)
    flow_headers = {
        "Authorization": f"Bearer {flow_token}",
        "Content-Type": "application/json",
    }

    # Step 3: Optionally patch kind:Skills
    if fix_kind:
        definition = patch_kind_skills(definition)

    patch_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}"
        f"?api-version=2016-11-01"
    )
    patch_body = {"properties": {"definition": definition}}
    patch_resp = requests.patch(patch_url, headers=flow_headers, json=patch_body)
    patch_resp.raise_for_status()

    # Step 4: Start the flow
    start_url = (
        f"{auth.flow_api_base}/providers/Microsoft.ProcessSimple"
        f"/environments/{env_id}/flows/{flow_id}/start"
        f"?api-version=2016-11-01"
    )
    start_resp = requests.post(start_url, headers=flow_headers)
    start_resp.raise_for_status()

    return {
        "flowId": flow_id,
        "environmentId": env_id,
        "name": name,
        "kindPatched": fix_kind,
        "started": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Import a Power Automate flow")
    parser.add_argument("--flow-json", required=True, help="Path to workflow.json")
    parser.add_argument("--name", required=True, help="Flow display name")
    parser.add_argument("--solution", help="Solution unique name (optional)")
    parser.add_argument("--no-fix-kind", action="store_true", help="Skip kind:Skills patching")
    parser.add_argument("--dataverse-url", default=os.environ.get("DATAVERSE_URL"))
    parser.add_argument("--cloud", default=os.environ.get("CPS_CLOUD"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID"))
    args = parser.parse_args()

    try:
        auth = FlowAuth(
            dataverse_url=args.dataverse_url,
            cloud=args.cloud,
            tenant_id=args.tenant_id,
        )
        result = import_flow(
            auth,
            flow_json_path=args.flow_json,
            name=args.name,
            solution=args.solution,
            fix_kind=not args.no_fix_kind,
        )
        print(json.dumps({"status": "ok", **result}, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
