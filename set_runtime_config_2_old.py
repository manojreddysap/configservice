import time
import requests
import json
import os
from main import force_worker_update, monitor_worker_update, trm_token_


# refer - https://wiki.one.int.sap/wiki/display/Avatar/TRM+Configuration+Service+APIs

# action = "WRITE"
# scope = "GLOBAL"  # scope of the configuration parameter that is being stored	GLOBAL/TENANT
# try:
#     tenant_name = "az-infra"
# except:
#     if scope == "GLOBAL":
#         pass
# system_id = "ziat001"
#
# entity = "nzdm"  # entity for configuration parameter
# key = "rfmTimeout"  # key for configuration parameter
# value = 10  # single value for configuration parameter
# try:
#     values = ""  # String array	multiple values for configuration parameter
# except:
#     pass
# valueType = "SINGLE"  # can be either SINGLE or MULTIPLE based on the param 'value' or 'values'

action = os.getenv("action")
scope = os.getenv("scope")
system_id = os.getenv("SYSTEM_ID")
tenant_name = os.getenv("TENANT")
entity = os.getenv("entity")
key = os.getenv("key")
value = os.getenv("value")
try:
    values = os.getenv("values")
except:
    pass
valueType = os.getenv("valueType")

ForceWorkerUpdate = os.getenv("ForceWorkerUpdate")
print(f"*******{ForceWorkerUpdate}****")

def read_config():
    with open('config.json') as f:
        conf = json.load(f)
    return conf


config = read_config()

cf_oauth_url = json.dumps(config[system_id]['cf_oauth_url']).strip('\"')
user = json.dumps(config[system_id]['user']).strip('\"')
cf_base_url = json.dumps(config[system_id]['cf_base_url']).strip('\"')
space_id = json.dumps(config[system_id]['space_id']).strip('\"')
trm_url = json.dumps(config[system_id]['trm_url']).strip('\"')
trm_oauth_url = json.dumps(config[system_id]['trm_oauth_url']).strip('\"')
trm_basic_auth = json.dumps(config[system_id]['trm_basic_auth']).strip('\"')


def trm_token():
    url = f"{trm_oauth_url}?grant_type=client_credentials"

    payload = {}
    headers = {
        'Authorization': f'Basic {trm_basic_auth}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    # print(response.text)
    res_in_dict = json.loads(response.text)
    return res_in_dict["access_token"]


def set_tenant_specific_worker_config():
    url = f"{trm_url}/configurations?scope={scope}&scopeId={tenant_name}"

    payload = json.dumps({
        "configurationParameters": [
            {
                "entity": f"{entity}",
                "key": f"{key}",
                "value": f"{value}",
                "valueType": f"{valueType}"
            },

        ],
        "scope": f"{scope}",
        "scopeId": f"{tenant_name}"
    })
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    response = requests.request("PUT", url, headers=headers, data=payload).status_code

    try:
        if response == 200:
            print(f"Configuration was successfully set on {tenant_name}. Verify below\n")
    except:
        print("Configuration setup was not possible. please check if you are passing correct parameters."
              "if any doubts please send a mail to infra")
    finally:
        return response


def get_tenant_specific_worker_config():
    url = f"{trm_url}/configurations?scope={scope}&scopeId={tenant_name}"

    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    result = json.loads(response.text)

    print(json.dumps(result, indent=4))


def get_global_worker_config():
    print("entering the function")
    url = f"{trm_url}/configurations?scope={scope}"
    print(f"url is {url}\n")

    payload = {}
    headers = {
        'Authorization': f'Bearer {token}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    result = json.loads(response.text)

    print(json.dumps(result, indent=4))

def set_global_worker_config():
    url = f"{trm_url}/configurations?scope={scope}"

    payload = json.dumps({
        "configurationParameters": [
            {
                "entity": f"{entity}",
                "key": f"{key}",
                "value": f"{value}",
                "valueType": f"{valueType}"
            },

        ],
        "scope": f"{scope}"
    })
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    response = requests.request("PUT", url, headers=headers, data=payload).status_code

    try:
        if response == 200:
            print(f"Configuration was successfully set on. Verify below\n")
    except:
        print("Configuration setup was not possible. please check if you are passing correct parameters."
              "if any doubts please send a mail to infra")
    finally:
        return response

token = trm_token()
# print(f"the token is {token}\n")


if scope == "TENANT":
    print("TENANT\n")
    if action == "READ":
        get_tenant_specific_worker_config()
    else:
        if set_tenant_specific_worker_config() == 200:
            time.sleep(5)
            get_tenant_specific_worker_config()

            time.sleep(5)
            if ForceWorkerUpdate == "true":
                print("Please Note: For the configurations to be registered. worker needs to be updated."
                      "Hence, worker update will start in 5sec")
                force_worker_update()
                while monitor_worker_update() != 0:
                    print("\n worker update is in progress")
                    time.sleep(25)
                print(f"\n{tenant_name} - update got completed")
            else:
                print("NOTE: you have set the config. however, if its on worker env. you will have to update the "
                      "worker for the chnages to register. else its not required")
        else:
            print(f"{set_tenant_specific_worker_config()} Configuration setup was not possible. please check if you "
                  f"are passing correct parameters. "
              "if any doubts please send a mail to infra")

elif scope == "GLOBAL":
    if action == "READ":
        print("GLOBAL\n")
        get_global_worker_config()
    elif action  == "WRITE":
        print("To set the configuration at global level contact - DL Prism Infra (mail)")

