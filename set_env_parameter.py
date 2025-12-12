#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# runtime check for requests dependency
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception as e:
    print("ERROR: Missing required Python package 'requests'.")
    print("Please run: pip3 install requests")
    print(f"Import error: {e}")
    sys.exit(20)


SET_JSON_FILE = "set_env_parameter.json"
READ_JSON_FILE = "tenant_credentials.json"
DEFAULT_APP_NAME = "it-design-service"

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def run_cmd(cmd: List[str], hide_cmd: bool = False) -> subprocess.CompletedProcess:
    if not hide_cmd:
        log(f"Running: {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    except subprocess.CalledProcessError as e:
        if not hide_cmd:
            log(f"Command failed ({e.returncode}): {' '.join(cmd)}")
            log(f"stdout: {e.stdout.strip()}")
            log(f"stderr: {e.stderr.strip()}")
        raise

def load_json_file(path: str) -> Any:
    if not os.path.isfile(path):
        log(f"ERROR: JSON file does not exist: {path}")
        sys.exit(2)
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)

def choose_tenant_entry_by_name(tenants: List[Dict[str, Any]], tenant_name: str) -> Optional[Dict[str, Any]]:
    for t in tenants:
        names = [
            t.get("name"),
            t.get("tenant"),
            t.get("tenantId"),
            t.get("tenant_id"),
            t.get("tenantName"),
            t.get("tenant_name")
        ]
        if any((n and n.strip().lower() == tenant_name.strip().lower()) for n in names if n):
            return t
    return None

def get_bearer_token(token_url: str, client_id: str, client_secret: str, timeout: int = 30) -> Dict[str, Any]:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }

    log(f"Requesting token from {token_url}")
    resp = session.post(token_url, data=data, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except Exception as e:
        log(f"Token request failed: {e}")
        log(f"Status: {resp.status_code}, body: {resp.text}")
        raise

    return resp.json()

def call_design_service(design_url: str, access_token: str, timeout: int = 30) -> None:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    log(f"Calling design service at {design_url}")
    resp = requests.get(design_url, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except Exception as e:
        log(f"Design service call failed: {e}")
        log(f"Status: {resp.status_code}, body: {resp.text}")
        raise
    log("Design service call successful.")
    log(f"Response sample: {resp.text[:200]}")

def set_env_parameter(design_url: str, access_token: str, app_name: str, value: str, timeout: int = 30) -> None:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {
        "appName": app_name,
        "envVarValue": value
    }
    log(f"Setting environment variable on {design_url} for app {app_name}")
    resp = requests.post(design_url, headers=headers, json=payload, timeout=timeout)
    try:
        resp.raise_for_status()
    except Exception as e:
        log(f"Set env param failed: {e}")
        log(f"Status: {resp.status_code}, body: {resp.text}")
        raise
    log("Environment parameter set successfully.")
    log(f"Response sample: {resp.text[:200]}")

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Set or read environment parameter using design service and tenant credentials.")
    parser.add_argument("--mode", choices=["set", "read"], required=True, help="set = set env param; read = read token usage")
    parser.add_argument("--landscape", required=True, help="Landscape (eu12, eu21, us31, ...)")
    parser.add_argument("--json-file", default="", help="Path to JSON file with tenant credentials")
    parser.add_argument("--value", help="Value to set (required for mode=set)")
    parser.add_argument("--app-name", default=DEFAULT_APP_NAME, help="Application name (for set mode)")
    parser.add_argument("--tenant", help="Tenant name (optional, for read mode)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv or sys.argv[1:])

    if args.debug:
        log(f"Args: {args}")

    if args.mode == "set" and not args.value:
        log("ERROR: mode=set requires --value")
        sys.exit(3)

    json_file = args.json_file or (SET_JSON_FILE if args.mode == "set" else READ_JSON_FILE)
    if not os.path.isfile(json_file):
        log(f"ERROR: specified json file not found: {json_file}")
        sys.exit(4)

    data = load_json_file(json_file)
    # expect data structure: { "tenants": [ { tenant entry }, ... ] } or a list directly
    tenants = []
    if isinstance(data, dict):
        if "tenants" in data and isinstance(data["tenants"], list):
            tenants = data["tenants"]
        else:
            # maybe a mapping of tenant->config, convert to list
            for k, v in data.items():
                if isinstance(v, dict):
                    v_copy = v.copy()
                    v_copy.setdefault("name", k)
                    tenants.append(v_copy)
    elif isinstance(data, list):
        tenants = data
    else:
        log("ERROR: JSON file has unexpected structure.")
        sys.exit(5)

    if args.tenant:
        tenant_entry = choose_tenant_entry_by_name(tenants, args.tenant)
        if not tenant_entry:
            log(f"ERROR: tenant '{args.tenant}' not found in json")
            sys.exit(6)
    else:
        # pick first tenant as default
        if not tenants:
            log("ERROR: no tenants found in json")
            sys.exit(7)
        tenant_entry = tenants[0]

    # Extract fields using common key variants
    client_id = tenant_entry.get("clientId") or tenant_entry.get("client_id") or tenant_entry.get("clientid")
    client_secret = tenant_entry.get("clientSecret") or tenant_entry.get("client_secret") or tenant_entry.get("clientsecret")
    token_url = tenant_entry.get("tokenurl") or tenant_entry.get("tokenUrl") or tenant_entry.get("token_url")
    design_url = tenant_entry.get("designServiceUrl") or tenant_entry.get("design_service_url")

    if not (client_id and client_secret and token_url and design_url):
        log("❌ ERROR: tenant config missing required fields.")
        log(f"Tenant keys: {list(tenant_entry.keys())}")
        sys.exit(13)

    token_payload = get_bearer_token(token_url, client_id, client_secret)
    access_token = token_payload.get("access_token")
    if not access_token:
        log("ERROR: token response did not contain access_token")
        log(f"Token response keys: {list(token_payload.keys())}")
        sys.exit(14)

    if args.mode == "set":
        set_env_parameter(design_url, access_token, args.app_name, args.value)
        log("✅ SET mode completed.")
    else:
        # read mode: call design service or token usage endpoint depending on tenant payload
        log("READ mode: fetching token usage / calling design service")
        # reuse get_bearer_token and call_design_service for simple read flow
        log("Token acquired; calling design service...")
        call_design_service(design_url, access_token)
        log("✅ READ mode completed.")

if __name__ == "__main__":
    main()
