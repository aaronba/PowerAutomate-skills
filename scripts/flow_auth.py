"""
flow_auth.py — Dual authentication for Dataverse Web API + Flow Management API.

Provides token acquisition for both APIs using azure-identity InteractiveBrowserCredential.
Supports commercial, GCC, and GCC-High clouds.

Usage:
    from flow_auth import FlowAuth
    auth = FlowAuth(dataverse_url="https://org123.crm9.dynamics.com", cloud="gcc")
    dv_token = auth.get_dataverse_token()
    flow_token = auth.get_flow_token()
"""

import os
import sys
from azure.identity import InteractiveBrowserCredential, ClientSecretCredential

CLOUD_CONFIG = {
    "public": {
        "dataverse_suffix": ".crm.dynamics.com",
        "flow_api_host": "api.flow.microsoft.com",
        "flow_scope": "https://service.flow.microsoft.com/.default",
        "login_authority": "https://login.microsoftonline.com",
    },
    "gcc": {
        "dataverse_suffix": ".crm9.dynamics.com",
        "flow_api_host": "gov.api.flow.microsoft.us",
        "flow_scope": "https://gov.service.flow.microsoft.us/.default",
        "login_authority": "https://login.microsoftonline.com",
    },
    "gcchigh": {
        "dataverse_suffix": ".crm.microsoftdynamics.us",
        "flow_api_host": "high.api.flow.microsoft.us",
        "flow_scope": "https://high.service.flow.microsoft.us/.default",
        "login_authority": "https://login.microsoftonline.us",
    },
}


def detect_cloud(dataverse_url: str) -> str:
    if not dataverse_url:
        return "public"
    if ".crm9.dynamics.com" in dataverse_url:
        return "gcc"
    if ".crm.microsoftdynamics.us" in dataverse_url:
        return "gcchigh"
    return "public"


class FlowAuth:
    def __init__(self, dataverse_url: str = None, cloud: str = None, tenant_id: str = None):
        self.dataverse_url = (dataverse_url or os.environ.get("DATAVERSE_URL", "")).rstrip("/")
        self.cloud = cloud or os.environ.get("CPS_CLOUD") or detect_cloud(self.dataverse_url)
        self.tenant_id = tenant_id or os.environ.get("TENANT_ID")
        self.config = CLOUD_CONFIG[self.cloud]

        client_id = os.environ.get("CLIENT_ID")
        client_secret = os.environ.get("CLIENT_SECRET")

        if client_id and client_secret and self.tenant_id:
            self._credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                authority=self.config["login_authority"],
            )
        else:
            kwargs = {}
            if self.tenant_id:
                kwargs["tenant_id"] = self.tenant_id
            if self.config["login_authority"] != "https://login.microsoftonline.com":
                kwargs["authority"] = self.config["login_authority"]
            self._credential = InteractiveBrowserCredential(**kwargs)

        self._dv_token = None
        self._flow_token = None

    def get_dataverse_token(self) -> str:
        scope = f"{self.dataverse_url}/.default"
        token = self._credential.get_token(scope)
        return token.token

    def get_flow_token(self) -> str:
        scope = self.config["flow_scope"]
        token = self._credential.get_token(scope)
        return token.token

    @property
    def flow_api_base(self) -> str:
        return f"https://{self.config['flow_api_host']}"
