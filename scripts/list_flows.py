"""
list_flows.py — List Power Automate cloud flows (category=5) in a Dataverse environment.

Usage:
    python list_flows.py --dataverse-url https://org123.crm9.dynamics.com
    python list_flows.py --bot-id <bot-id>
    python list_flows.py --all   # include disabled flows
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

SELECT_FIELDS = "workflowid,name,statecode,statuscode,modifiedon,_ownerid_value,description"


def list_flows(auth: FlowAuth, bot_id: str = None, include_all: bool = False) -> dict:
    dv_token = auth.get_dataverse_token()
    headers = {**DV_HEADERS, "Authorization": f"Bearer {dv_token}"}

    filters = ["category eq 5"]
    if not include_all:
        filters.append("statecode eq 0")

    url = (
        f"{auth.dataverse_url}/api/data/v9.2/workflows"
        f"?$filter={' and '.join(filters)}"
        f"&$select={SELECT_FIELDS}"
        f"&$orderby=modifiedon desc"
    )

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    flows = resp.json().get("value", [])

    if bot_id:
        # Filter flows whose clientdata references the bot
        filtered = []
        for flow in flows:
            detail_url = (
                f"{auth.dataverse_url}/api/data/v9.2/workflows({flow['workflowid']})"
                f"?$select=clientdata"
            )
            detail_resp = requests.get(detail_url, headers=headers)
            if detail_resp.ok:
                clientdata = detail_resp.json().get("clientdata", "")
                if bot_id in clientdata:
                    filtered.append(flow)
        flows = filtered

    return {"status": "ok", "count": len(flows), "flows": flows}


def main():
    parser = argparse.ArgumentParser(description="List Power Automate cloud flows")
    parser.add_argument("--dataverse-url", default=os.environ.get("DATAVERSE_URL"))
    parser.add_argument("--cloud", default=os.environ.get("CPS_CLOUD"))
    parser.add_argument("--tenant-id", default=os.environ.get("TENANT_ID"))
    parser.add_argument("--bot-id", help="Filter flows linked to a specific agent")
    parser.add_argument("--all", action="store_true", help="Include disabled flows")
    args = parser.parse_args()

    try:
        auth = FlowAuth(
            dataverse_url=args.dataverse_url,
            cloud=args.cloud,
            tenant_id=args.tenant_id,
        )
        result = list_flows(auth, bot_id=args.bot_id, include_all=args.all)
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
