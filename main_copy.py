import time
import requests
import json
import os

# tenant_name = "katest-egesb-perf"
# system_id = "ziat001"
apps = ["it-trm", "it-config"]
# folder_path = "C:\\MC_files\\MC\\certificate_keys"
folder_path = "D:\\GITSync\\infra\\certificates"

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
password = json.dumps(config[system_id]['password']).strip('\"')


# def trm_token():
#     url = f"{trm_oauth_url}?grant_type=client_credentials"
#
#     payload = {}
#     headers = {
#         'Authorization': f'Basic {trm_basic_auth}'
#     }
#
#     response = requests.request("GET", url, headers=headers, data=payload).json()
#
#     # print(response.text)
#     # res_in_dict = json.loads(response.text)
#
#     print(response)
#     return response["access_token"]

def cf_oauth_token():
    url = f"{cf_oauth_url}/oauth/token"

    payload = f"grant_type=password&client_id=cf&client_secret=&username={user}&password={password}"
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    # print(response.text)
    return (requests.request("POST", url, headers=headers, data=payload)).json()["access_token"]


token = cf_oauth_token()


def get_app_guid(token, app):
    try:
        url = f"{cf_base_url}/v3/apps?page=1&per_page=1000&space_guids={space_id}&names={app}"

        payload = {}
        headers = {
            'Authorization': f'Bearer {token}'
            # 'Cookie': 'JTENANTSESSIONID_kr19bxkapa=FPtRDK1dM3D1lD56pq9oAq9mvHn19ohxqXjClhqrbLI%3D'
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        guid = json.loads(response.text)["resources"][0]["guid"]

        print(f"guid is: {guid}")

        return guid
    except:
        print(f"\n unable to fetch guid for {app}. There might couple of reasons for this - \n"
              f"1. Software Update might be in progress Or\n"
              f"2. There might be some deployment issue due to which there might be some duplication of applications.\n"
              f"3. Application name might be incorrect\n"
              f"Please contact Infra team to understand the root cause and resolution for the same"
              )


# guid = get_app_guid(token, app)


# print(oauth_token)

def get_app_env_var(guid, token):
    url = f"{cf_base_url}/v3/apps/{guid}/env"

    payload = {}
    headers = {
        'Authorization': f'Bearer {token}'
    }

    try:
        response = \
        requests.request("GET", url, headers=headers, data=payload).json()["system_env_json"]["VCAP_SERVICES"]["xsuaa"][0]["credentials"]

        if "elmo" in response["xsappname"]:
            response = requests.request("GET", url, headers=headers, data=payload).json()["system_env_json"]["VCAP_SERVICES"]["xsuaa"][1]["credentials"]
        print(f"response is :\n {response}")

        client_id = response["clientid"]
        # print(f"clientid is: {client_id}")

        certificate = response["certificate"]
        # print(f"certificate is {certificate}")

        certurl = response["certurl"]

        key = response["key"]

        # print(f"client_id: {clientid}\n")
        # print(f"certurl:\n {certurl}\n")
        # print(f"certificate:\n {certificate}\n")
        # print(f"key:\n {key}\n")
        #
        # # Open a file in write mode using the `with` statement
        # with open("certificate.pem", "w") as f:
        #     # Use the `write()` method to store the data in the file
        #     f.write(certificate)
        # # The file is automatically closed after the `with` block is executed
        #
        # # Open a file in write mode using the `with` statement
        # with open("key.pem", "w") as f:
        #     # Use the `write()` method to store the data in the file
        #     f.write(key)
        # # The file is automatically closed after the `with` block is executed

        return client_id, certurl, certificate, key
    except KeyError:
        response = \
            requests.request("GET", url, headers=headers, data=payload).json()["system_env_json"]["VCAP_SERVICES"][
                "xsuaa"][
                1]["credentials"]

        print(f"response is :\n {response}")

        client_id = response["clientid"]
        # print(f"clientid is: {client_id}")

        certificate = response["certificate"]
        # print(f"certificate is {certificate}")

        certurl = response["certurl"]

        key = response["key"]

        return client_id, certurl, certificate, key

    # print(json.dumps(response, indent=4))


#client_id, certurl, certificate, key = get_app_env_var()


# print(certurl)


def get_jwt_x509(certurl, client_id, certificate, key, folder_path):
    auth_url = certurl + "/oauth/token?grant_type=client_credentials"
    payload = "client_id=" + client_id
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Check if the folder exists, and create it if it does not
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Set the file path
    file_path1 = os.path.join(folder_path, f'{system_id}_certificate.pem')
    file_path2 = os.path.join(folder_path, f'{system_id}_key.pem')

    cert_file = open(file_path1, "w")
    cert_file.write(certificate)
    cert_file.close()

    key_file = open(file_path2, "w")
    key_file.write(key)
    key_file.close()

    print("making api call...")
    response = requests.post(auth_url, data=payload, headers=headers, cert=(file_path1, file_path2))
    print("done.\n")

    print(f"STATUS_CODE = {response.status_code}")
    print("token:\n", response.json())
    return response.json()["access_token"]


#get_jwt_x509(certurl, client_id, certificate, key, folder_path)
#access_token = get_jwt_x509(certurl, client_id, certificate, key, folder_path)
#print(f"access_token of {app} is:\n {access_token}")


def force_worker_update(access_token_trm):

    url = f"{trm_url}/tenant-softwares/tenants?tenantNames={tenant_name}"

    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token_trm}'
    }

    response = requests.request("PUT", url, headers=headers)
    time.sleep(5)

    print(response.json())


def monitor_worker_update(access_token_trm):
    url = f"{trm_url}/tenant-softwares/tasks?tenantNames={tenant_name}"

    payload = ""
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token_trm}'
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


def get_access_tokens_for_apps(apps, token):
    access_tokens = {}  # Dictionary to store the access tokens for each app

    for app in apps:
        print(f"Processing {app}...")

        # Get the GUID for the app
        guid = get_app_guid(token, app)

        if guid:
            # Get environment variables
            client_id, certurl, certificate, key = get_app_env_var(guid, token)

            # Get access token using the cert data
            access_token = get_jwt_x509(certurl, client_id, certificate, key, folder_path)

            # Store the access token for the current app
            access_tokens[app] = access_token
            print(f"Access token for {app} is:\n{access_token}")
        else:
            print(f"Skipping {app} due to issues with fetching GUID.\n")

    return access_tokens


# Usage
access_tokens = get_access_tokens_for_apps(apps, token)

# Fetching values using the keys
access_token_trm = access_tokens['it-trm']
access_token_config = access_tokens['it-config']


if __name__ == "__main__":
    token = cf_oauth_token()
    access_tokens = get_access_tokens_for_apps(apps, token)
   #guid = get_app_guid(token, app)
   #client_id, certurl, certificate, key = get_app_env_var()
   #access_token = get_jwt_x509(certurl, client_id, certificate, key, folder_path)
    start_time = time.time()
    force_worker_update(access_token_trm)
    while monitor_worker_update(access_token_trm) != 0:
        print("\n worker update is in progress")
        time.sleep(30)

    end_time = time.time()
    total_time_taken = start_time - end_time
    print(f"\n{tenant_name} - update got completed in {total_time_taken}")
