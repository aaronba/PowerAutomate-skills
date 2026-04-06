"""
export_flow.py — Export a Power Automate flow definition from Dataverse to local files.

Usage:
    python export_flow.py --flow-id <guid>
    python export_flow.py --flow-id <guid> --output-dir ./my-flows
    python export_flow.py --all
"""

import argparse
import json
import os
import re
import sys

import requests
import yaml
from flow_auth import FlowAuth

DV_HEADERS = {
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}

WORKFLOW_SELECT = (
    "workflowid,name,clientdata,statecode,statuscode,"
    "category,type,description,primaryentity,modifiedon"
)


def sanitize_name(name: str) -> str:
    return re.sub(r'[^\w\-.]', '_', name).strip('_')[:80]


def export_single_flow(auth: FlowAuth, flow_id: str, output_dir: str) -> dict:
    dv_token = auth.get_dataverse_token()
    headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}

    url = (
        f"{auth.dataverse_url}/api/data/v9.2/workflows({flow_id})"
        f"?$select={WORKFLOW_SELECT}"
    )
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    workflow = resp.json()

    flow_name = sanitize_name(workflow.get("name", "unnamed"))
    folder = os.path.join(output_dir, f"{flow_name}-{flow_id}")
    os.makedirs(folder, exist_ok=True)

    # Write clientdata as workflow.json
    clientdata_raw = workflow.get("clientdata", "{}")
    try:
        clientdata = json.loads(clientdata_raw)
    except (json.JSONDecodeError, TypeError):
        clientdata = clientdata_raw

    workflow_path = os.path.join(folder, "workflow.json")
    with open(workflow_path, "w", encoding="utf-8") as f:
        json.dump(clientdata, f, indent=2, ensure_ascii=False)

    # Write metadata.yml
    metadata = {
        "workflowId": workflow.get("workflowid"),
        "name": workflow.get("name"),
        "type": workflow.get("type"),
        "description": workflow.get("description"),
        "statecode": workflow.get("statecode"),
        "statuscode": workflow.get("statuscode"),
        "category": workflow.get("category"),
        "primaryentity": workflow.get("primaryentity"),
        "modifiedon": workflow.get("modifiedon"),
    }
    metadata_path = os.path.join(folder, "metadata.yml")
    with open(metadata_path, "w", encoding="utf-8") as f:
        yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)

    return {
        "flowId": flow_id,
        "name": workflow.get("name"),
        "folder": folder,
        "files": ["workflow.json", "metadata.yml"],
    }


def export_all_flows(auth: FlowAuth, output_dir: str) -> list:
    dv_token = auth.get_dataverse_token()
    headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}

    url = (
        f"{auth.dataverse_url}/api/data/v9.2/workflows"
        f"?$filter=category eq 5"
        f"&$select=workflowid,name"
    )
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    flows = resp.json().get("value", [])

    results = []
    for flow in flows:
        fid = flow["workflowid"]
        result = export_single_flow(auth, fid, output_dir)
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description="Export Power Automate flow definitions")
    parser.add_argument("--flow-id", help="Workflow ID to export")
    parser.add_argument("--all", action="store_true", help="Export all category-5 flows")
    parser.add_argument("--output-dir", default="./workflows", help="Output directory")
    parser.add_argument("--dataverse-url", default=os.environ.get("DATAVERSE_URL"))
    parser.add_argument("--cloud", default=os.environ.get("CPS_CLOUD"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID"))
    args = parser.parse_args()

    if not args.flow_id and not args.all:
        parser.error("Provide --flow-id or --all")

    try:
        auth = FlowAuth(
            dataverse_url=args.dataverse_url,
            cloud=args.cloud,
            tenant_id=args.tenant_id,
        )

        if args.all:
            exported = export_all_flows(auth, args.output_dir)
            result = {"status": "ok", "count": len(exported), "exported": exported}
        else:
            exported = export_single_flow(auth, args.flow_id, args.output_dir)
            result = {"status": "ok", "exported": exported}

        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
