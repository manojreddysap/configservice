#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

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

def create_requests_session() -> requests.Session:
    s = requests.Session()
    r = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=r))
    s.mount("http://", HTTPAdapter(max_retries=r))
    return s

def load_json_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        log(f"❌ ERROR: JSON file not found: {path}")
        sys.exit(1)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        log(f"❌ ERROR: Failed to parse JSON {path}: {e}")
        sys.exit(2)
    except Exception as e:
        log(f"❌ ERROR reading {path}: {e}")
        sys.exit(3)

def find_landscape(cfg: Dict[str, Any], landscape: str) -> Optional[Dict[str, Any]]:
    for l in cfg.get("landscapes", []):
        if str(l.get("landscape", "")).strip() == landscape:
            return l
    for l in cfg.get("landscapes", []):
        api = str(l.get("cfApiEndpoint", "")).lower()
        if landscape.lower() in api:
            return l
    return None

def find_tenant_config(cfg: Dict[str, Any], landscape: str, tenant_name: Optional[str] = None) -> Dict[str, Any]:
    land_entry = find_landscape(cfg, landscape)
    if land_entry is None:
        available = [l.get("landscape") for l in cfg.get("landscapes", [])]
        log(f"❌ ERROR: Landscape '{landscape}' not found in JSON config.")
        log(f"Available landscapes: {available}")
        sys.exit(5)

    tenants = land_entry.get("tenants", [])
    if not tenants:
        log(f"❌ ERROR: No tenants configured for landscape '{landscape}'.")
        sys.exit(6)

    if tenant_name:
        for t in tenants:
            if t.get("name") == tenant_name:
                return t
        avail = [t.get("name") for t in tenants]
        log(f"❌ ERROR: Tenant '{tenant_name}' not found under landscape '{landscape}'.")
        log(f"Available tenants for '{landscape}': {avail}")
        sys.exit(7)

    log(f"No --tenant provided; defaulting to the first tenant for '{landscape}': {tenants[0].get('name')}")
    return tenants[0]

def cf_login(api: str, org: str, space: str, username: str, password: str) -> None:
    log("Logging into Cloud Foundry...")
    run_cmd(["cf", "api", api, "--skip-ssl-validation"])
    run_cmd(["cf", "login", "-u", username, "-p", password, "-o", org, "-s", space], hide_cmd=True)

def cf_set_env(app_name: str, env_name: str, env_value: str) -> None:
    log(f"Setting environment variable {env_name} on app {app_name} ...")
    run_cmd(["cf", "set-env", app_name, env_name, env_value])

def cf_restage(app_name: str) -> None:
    log(f"Restaging {app_name} ...")
    run_cmd(["cf", "restage", app_name])

def get_bearer_token(token_url: str, client_id: str, client_secret: str) -> Dict[str, Any]:
    sess = create_requests_session()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
    log(f"Requesting token from {token_url}...")
    try:
        resp = sess.post(token_url, data=data, headers=headers, timeout=20)
    except Exception as e:
        log(f"❌ Token request failed: {e}")
        sys.exit(8)
    if resp.status_code != 200:
        log(f"❌ Token endpoint returned {resp.status_code}: {resp.text}")
        sys.exit(9)
    payload = resp.json()
    if "access_token" not in payload:
        log(f"❌ Token response missing access_token: {payload}")
        sys.exit(10)
    return payload

def call_design_service(design_url: str, access_token: str) -> None:
    sess = create_requests_session()
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    log(f"Calling design service: {design_url}")
    try:
        resp = sess.get(design_url, headers=headers, timeout=30)
    except Exception as e:
        log(f"❌ Design service call failed: {e}")
        sys.exit(11)
    if resp.status_code >= 400:
        log(f"❌ Design service returned {resp.status_code}: {resp.text}")
        sys.exit(12)
    ct = resp.headers.get("Content-Type", "")
    if "application/json" in ct:
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)
    else:
        print(resp.text)

def main() -> None:
    parser = argparse.ArgumentParser(description="Set env or read token usage")
    parser.add_argument("--mode", required=True, choices=["set", "read"])
    parser.add_argument("--landscape", required=True)
    parser.add_argument("--value")
    parser.add_argument("--tenant")
    parser.add_argument("--json-file")
    parser.add_argument("--app-name", default=os.environ.get("APP_NAME", DEFAULT_APP_NAME))
    args = parser.parse_args()

    mode = args.mode
    landscape = args.landscape
    tenant_name = args.tenant
    json_file = args.json_file

    if json_file:
        chosen_json = json_file
    else:
        chosen_json = SET_JSON_FILE if mode == "set" else READ_JSON_FILE

    log(f"Mode={mode} | Landscape={landscape} | JSON={chosen_json}")
    cfg = load_json_file(chosen_json)

    if mode == "set":
        if not args.value:
            log("❌ ERROR: --value is required in mode=set")
            sys.exit(1)

        land_entry = find_landscape(cfg, landscape)
        if not land_entry:
            available = [l.get("landscape") for l in cfg.get("landscapes", [])]
            log(f"❌ ERROR: Landscape '{landscape}' not found. Available: {available}")
            sys.exit(4)

        cf_api = str(land_entry.get("cfApiEndpoint", ""))
        cf_org = str(land_entry.get("cfOrg", ""))
        cf_space = str(land_entry.get("cfSpace", ""))
        p_user = str(land_entry.get("PUserName", ""))
        p_pass = str(land_entry.get("PPassword", ""))
        env_var_name = str(land_entry.get("env_variable_name", ""))

        log("Resolved CF entry.")
        log(f"API: {cf_api}")
        log(f"Org/Space: {cf_org} / {cf_space}")
        log(f"User: {p_user}")
        log(f"Env Var: {env_var_name}")
        log(f"Value: {args.value}")

        try:
            cf_login(cf_api, cf_org, cf_space, p_user, p_pass)
            cf_set_env(args.app_name, env_var_name, args.value)
            cf_restage(args.app_name)
            log("✅ SET mode completed.")
        finally:
            try:
                run_cmd(["cf", "logout"])
            except Exception:
                pass
        return

    tenant_entry = find_tenant_config(cfg, landscape, tenant_name)
    client_id = tenant_entry.get("clientId") or tenant_entry.get("client_id")
    client_secret = tenant_entry.get("clientSecret") or tenant_entry.get("client_secret")
    token_url = tenant_entry.get("tokenurl") or tenant_entry.get("tokenUrl") or tenant_entry.get("token_url")
    design_url = tenant_entry.get("designServiceUrl") or tenant_entry.get("design_service_url")

    if not (client_id and client_secret and token_url and design_url):
        log("❌ ERROR: tenant config missing required fields.")
        log(f"Tenant keys: {list(tenant_entry.keys())}")
        sys.exit(13)

    token_payload = get_bearer_token(token_url, client_id, client_secret)
    access_token = token_payload.get("access_token")
    log("Token acquired; calling design service...")
    call_design_service(design_url, access_token)
    log("✅ READ mode completed.")

if __name__ == "__main__":
    main()
