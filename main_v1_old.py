import time
import requests
import json
import os

# tenant_name = "katest-egesb-perf"
# system_id = "acdev002"
system_id = os.getenv("SYSTEM_ID")
tenant_name = os.getenv("TENANT")


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

    response = requests.request("GET", url, headers=headers, data=payload).json()

    # print(response.text)
    # res_in_dict = json.loads(response.text)
    
    print(response)
    return response["access_token"]


trm_token_ = trm_token()


def force_worker_update():
    url = f"{trm_url}/tenant-softwares/tenants?tenantNames={tenant_name}"

    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {trm_token_}'
    }

    response = requests.request("PUT", url, headers=headers)
    time.sleep(5)
    
    print(response.json())


def monitor_worker_update():

    url = f"{trm_url}/tenant-softwares/tasks?tenantNames={tenant_name}"

    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {trm_token_}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.json())

    in_progress = response.json()["inProgress"]
    return in_progress

# start_time = time.time()
# force_worker_update()

# while monitor_worker_update() != 0:
#     print("\n worker update is in progress")
#     time.sleep(30)
#
# end_time = time.time()
# total_time_taken = start_time - end_time
# print(f"\n{tenant_name} - update got completed in {total_time_taken}")


if __name__ == "__main__":
    trm_token_ = trm_token()
    start_time = time.time()
    force_worker_update()
    while monitor_worker_update() != 0:
        print("\n worker update is in progress")
        time.sleep(30)

    end_time = time.time()
    total_time_taken = start_time - end_time
    print(f"\n{tenant_name} - update got completed in {total_time_taken}")
