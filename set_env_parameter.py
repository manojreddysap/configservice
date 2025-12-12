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
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
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
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def choose_tenant_entry_by_name(
    tenants: List[Dict[str, Any]], tenant_name: str
) -> Optional[Dict[str, Any]]:
    for t in tenants:
        names = [
            t.get("name"),
            t.get("tenant"),
            t.get("tenantId"),
            t.get("tenant_id"),
            t.get("tenantName"),
            t.get("tenant_name"),
        ]
        if any(
            (n and n.strip().lower() == tenant_name.strip().lower())
            for n in names
            if n
        ):
            return t
    return None


def extract_tenants_from_json(data: Any, landscape: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Supports multiple JSON structures and robust landscape fallback:
      - {"tenants": [...]}
      - [ {...}, {...} ]
      - {"landscapes": [ {"landscape":"eu12","tenants":[...]}, ... ]}
      - {"eu12": {"tenants":[...]}, ...}
    Fallbacks:
      - exact match
      - if landscape contains '-', try prefix (eu12-fun -> eu12)
      - startswith matching
    """
    # Case A: dict with "tenants"
    if isinstance(data, dict) and "tenants" in data and isinstance(data["tenants"], list):
        return data["tenants"]

    # Case B: top-level list
    if isinstance(data, list):
        return data

    # Helper to extract tenants from a landscape object
    def tenants_from_landscape_obj(obj):
        if not isinstance(obj, dict):
            return []
        t = obj.get("tenants")
        if isinstance(t, list):
            return t
        for key in ("tenantList", "tenantsList"):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
        return []

    # Case C: landscapes array
    if isinstance(data, dict) and "landscapes" in data and isinstance(data["landscapes"], list):
        landscapes = data["landscapes"]

        # exact match
        if landscape:
            for l in landscapes:
                lname = None
                if isinstance(l, dict):
                    lname = l.get("landscape") or l.get("name") or l.get("id")
                if lname and lname.strip().lower() == landscape.strip().lower():
                    return tenants_from_landscape_obj(l)

        # dash-prefix fallback
        if landscape and "-" in landscape:
            prefix = landscape.split("-", 1)[0].strip().lower()
            for l in landscapes:
                lname = None
                if isinstance(l, dict):
                    lname = l.get("landscape") or l.get("name") or l.get("id")
                if lname and lname.strip().lower() == prefix:
                    return tenants_from_landscape_obj(l)

        # startswith fallback
        if landscape:
            ls = landscape.strip().lower()
            for l in landscapes:
                lname = None
                if isinstance(l, dict):
                    lname = l.get("landscape") or l.get("name") or l.get("id")
                if lname and lname.strip().lower().startswith(ls):
                    return tenants_from_landscape_obj(l)

        # fallback: first landscape tenants (useful for MODE=set fallback)
        if landscapes:
            return tenants_from_landscape_obj(landscapes[0])

        return []

    # Case D: mapping of landscape -> object
    if isinstance(data, dict):
        # direct key match
        if landscape and landscape in data:
            candidate = data[landscape]
            if isinstance(candidate, dict) and isinstance(candidate.get("tenants"), list):
                return candidate["tenants"]
            if isinstance(candidate, list):
                return candidate

        # dash-prefix fallback
        if landscape and "-" in landscape:
            prefix = landscape.split("-", 1)[0].strip()
            if prefix in data:
                candidate = data[prefix]
                if isinstance(candidate, dict) and isinstance(candidate.get("tenants"), list):
                    return candidate["tenants"]
                if isinstance(candidate, list):
                    return candidate

        # fallback: convert dict to list of tenant dicts
        potential = []
        for k, v in data.items():
            if isinstance(v, dict):
                copy = v.copy()
                copy.setdefault("name", k)
                potential.append(copy)
        if potential:
            return potential

    return []


def list_landscapes_and_tenants(data: Any) -> None:
    """
    Print a helpful listing of landscapes and their tenant names for debugging.
    """
    if isinstance(data, dict) and "landscapes" in data and isinstance(data["landscapes"], list):
        log("Detected 'landscapes' structure:")
        for l in data["landscapes"]:
            if not isinstance(l, dict):
                continue
            lname = l.get("landscape") or l.get("name") or l.get("id") or "(unnamed)"
            tenants = l.get("tenants") or []
            log(f" - {lname}: {len(tenants)} tenant(s)")
            for t in tenants:
                log(f"    * {t.get('name') or t.get('tenant') or '(no-name)'}")
        return

    # other structures
    if isinstance(data, dict):
        log("Detected dict-style structure; listing top-level keys and any tenant lists discovered:")
        for k, v in data.items():
            if isinstance(v, dict) and isinstance(v.get("tenants"), list):
                log(f" - {k} -> {len(v.get('tenants'))} tenants")
                for t in v.get('tenants'):
                    log(f"    * {t.get('name') or t.get('tenant') or '(no-name)'}")
            elif isinstance(v, list):
                log(f" - {k} -> list of length {len(v)} (top-level list candidate)")
        return

    if isinstance(data, list):
        log("Detected top-level list of tenants:")
        for t in data:
            if isinstance(t, dict):
                log(f" - {t.get('name') or t.get('tenant') or '(no-name)'}")
        return

    log("Unrecognized JSON structure for tenant listing.")


def get_bearer_token(token_url: str, client_id: str, client_secret: str, timeout: int = 30) -> Dict[str, Any]:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}

    log(f"Requesting token from {token_url}")
    resp = session.post(token_url, data=data, headers=headers, timeout=timeout)

    try:
        resp.raise_for_status()
    except Exception as e:
        log(f"Token request failed: {e}")
        log(f"Status: {resp.status_code}, Body: {resp.text}")
        raise

    return resp.json()


def set_env_parameter(design_url: str, access_token: str, app_name: str, value: str, timeout: int = 30) -> None:
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    payload = {"appName": app_name, "envVarValue": value}
    log(f"Setting environment parameter for {app_name} on {design_url}")
    resp = requests.post(design_url, json=payload, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except Exception as e:
        log(f"Set env parameter failed: {e}")
        log(f"Status: {resp.status_code}, Body: {resp.text}")
        raise
    log("Environment parameter updated successfully.")
    log(f"Response snippet: {resp.text[:200]}")


def call_design_service(design_url: str, access_token: str, timeout: int = 30) -> None:
    headers = {"Authorization": f"Bearer {access_token}"}
    log(f"Calling design service: {design_url}")
    resp = requests.get(design_url, headers=headers, timeout=timeout)
    try:
        resp.raise_for_status()
    except Exception as e:
        log(f"Design service call failed: {e}")
        log(f"Status: {resp.status_code}, Body: {resp.text}")
        raise
    log("Design service responded successfully.")
    log(f"Response snippet: {resp.text[:200]}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Set or read environment parameter using design service and tenant credentials.")
    parser.add_argument("--mode", choices=["set", "read"], required=False, help="set = set env param; read = read token usage")
    parser.add_argument("--landscape", required=False, help="Landscape (eu12, eu21, us31, ...)")
    parser.add_argument("--json-file", default="", help="Path to JSON file with tenant credentials")
    parser.add_argument("--value", help="Value to set (required for mode=set)")
    parser.add_argument("--app-name", default=DEFAULT_APP_NAME, help="Application name (for set mode)")
    parser.add_argument("--tenant", help="Tenant name (optional, for read mode)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--list-tenants", action="store_true", help="List detected landscapes and tenants from JSON and exit")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])

    if args.debug:
        log(f"Arguments: {args}")

    # if user asked to list tenants, only do that and exit
    json_file = args.json_file or (SET_JSON_FILE if args.mode == "set" else READ_JSON_FILE)
    if args.list_tenants:
        if not os.path.isfile(json_file):
            log(f"ERROR: JSON file not found: {json_file}")
            sys.exit(4)
        data = load_json_file(json_file)
        list_landscapes_and_tenants(data)
        sys.exit(0)

    # enforce mutual exclusivity
    if args.value and args.tenant:
        log("ERROR: Provide either --value (for MODE=set) or --tenant (for MODE=read), but not both.")
        sys.exit(21)

    # require mode and landscape in normal runs
    if not args.mode:
        log("ERROR: --mode is required. Use --mode set|read")
        sys.exit(2)
    if not args.landscape:
        log("ERROR: --landscape is required")
        sys.exit(2)

    if args.mode == "set" and not args.value:
        log("ERROR: mode=set requires --value")
        sys.exit(3)

    json_file = args.json_file or (SET_JSON_FILE if args.mode == "set" else READ_JSON_FILE)
    if not os.path.isfile(json_file):
        log(f"ERROR: specified json file not found: {json_file}")
        sys.exit(4)

    data = load_json_file(json_file)

    tenants = extract_tenants_from_json(data, landscape=args.landscape)
    if args.debug:
        log(f"Extracted {len(tenants)} tenant entries (after landscape selection)")

    # If no tenants found:
    if not tenants:
        # For set mode, fall back to first landscape's tenants if available (conservative auto-fix)
        if args.mode == "set":
            log(f"WARNING: no tenants found in json for landscape '{args.landscape}'. Attempting fallback to first available landscape.")
            # extract tenants without specifying landscape to get first available (function returns first landscape tenants)
            tenants = extract_tenants_from_json(data, landscape=None)
            if tenants:
                log(f"Fallback succeeded: using first landscape which has {len(tenants)} tenant(s). Proceeding with first tenant.")
            else:
                log(f"ERROR: no tenants available anywhere in JSON. Aborting.")
                sys.exit(7)
        else:
            # read mode requires explicit tenant (do not auto-fix)
            log(f"ERROR: no tenants found in json for landscape '{args.landscape}'")
            sys.exit(7)

    if args.tenant:
        tenant_entry = choose_tenant_entry_by_name(tenants, args.tenant)
        if not tenant_entry:
            log(f"ERROR: tenant '{args.tenant}' not found in json for landscape '{args.landscape}'")
            log("Available tenants for this landscape:")
            for t in tenants:
                log(f" - {t.get('name') or t.get('tenant') or '(unknown)'}")
            sys.exit(6)
    else:
        tenant_entry = tenants[0]
        log(f"No --tenant provided; defaulting to first tenant: {tenant_entry.get('name') or tenant_entry.get('tenant')}")

    client_id = (
        tenant_entry.get("clientId")
        or tenant_entry.get("client_id")
        or tenant_entry.get("clientid")
    )
    client_secret = (
        tenant_entry.get("clientSecret")
        or tenant_entry.get("client_secret")
        or tenant_entry.get("clientsecret")
    )
    token_url = (
        tenant_entry.get("tokenurl")
        or tenant_entry.get("tokenUrl")
        or tenant_entry.get("token_url")
    )
    design_url = (
        tenant_entry.get("designServiceUrl")
        or tenant_entry.get("design_service_url")
        or tenant_entry.get("designUrl")
    )

    if not (client_id and client_secret and token_url and design_url):
        log("ERROR: tenant entry missing required fields (clientId/clientSecret/tokenurl/designServiceUrl)")
        sys.exit(13)

    token_data = get_bearer_token(token_url, client_id, client_secret)
    access_token = token_data.get("access_token")
    if not access_token:
        log("ERROR: no access_token in token response")
        sys.exit(14)

    if args.mode == "set":
        set_env_parameter(design_url, access_token, args.app_name, args.value)
        log("SET mode completed")
    else:
        call_design_service(design_url, access_token)
        log("READ mode completed")


if __name__ == "__main__":
    main()
