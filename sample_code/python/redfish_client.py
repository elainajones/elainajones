import os
import time
import json
import re
import urllib3

import requests
from requests.models import Response
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


class RedFish:
    """Redfish client wrapper.

    Convenience wrapper for Redfish to extend and define common methods
    for managing a Redfish connection.

    Attributes:
        client: Refish client object
        default_prefix: Redfish API root URI
    """
    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        port=443,
    ) -> None:
        """Initializes the Redfish client connection.

        Args:
            hostname: Redfish host IP address (i.e. BMC).
            username: Redfish user (i.e. BMC).
            password: Redfish password (i.e. BMC).
        """

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Store values for later so we can reconnect automatically if needed.
        self.__hostname = hostname
        self.__username = username
        self.__password = password
        self.__port = port

        self.prefix = '/redfish/v1'
        self.base_url = f'https://{self.__hostname}:{self.__port}'

        self.__auth()

    def __auth(self) -> None:
        """Establishes client Redfish connection.

        """
        self.client = requests.Session()
        self.client.verify = False
        self.client.auth = (self.__username, self.__password)

        retries = retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[408, 500]
        )
        # Builtin retry mechanism
        self.client.mount('https://', HTTPAdapter(max_retries=retries))
        self.client.mount('http://', HTTPAdapter(max_retries=retries))

    def __timeout_response(self):
        """Make a response object for requests that timeout.

        """
        empty_response = Response()
        empty_response.status_code = 408
        empty_response._content = b''

        return empty_response

    def get(self, url, **kwargs) -> object:
        """Perform a GET request.

        Convenience wrapper for redfish.redfish_client.get that handles
        re-authentication.

        Returns:
            returns a rest request with method 'Get'
        """

        url = self.base_url + url

        k = {**kwargs}
        k['timeout'] = k.get('timeout', 30)

        try:
            res = self.client.get(url, **k)
            # The session probably timed out. Need to re-authenticate.
            if res.status_code == 401:
                self.__auth()
                # Try the request again
                res = self.client.get(url, **k)

        except requests.exceptions.ReadTimeout:
            # Timeout waiting for a response. Return an appropriate
            # response and move on to avoid breaking on edge-cases.
            res = self.__timeout_response()

        return res

    def patch(self, *args, **kwargs) -> object:
        """Perform a PATCH request.

        Convenience wrapper for redfish.redfish_client.patch that handles
        re-authentication.

        Returns:
            returns a rest request with method 'Patch'
        """
        res = self.client.patch(*args, **kwargs)

        # The session probably timed out. Need to re-authenticate.
        if res.status_code == 401:
            self.__auth()
            # Try the request again
            res = self.client.patch(*args, **kwargs)

        return res

    def post(self, url, **kwargs) -> object:
        """Perform a POST request.

        Convenience wrapper for redfish.redfish_client.post that handles
        re-authentication.

        Returns:
            returns a rest request with method 'Post'
        """
        url = self.base_url + url
        res = self.client.post(url, **kwargs)

        # The session probably timed out. Need to re-authenticate.
        if res.status_code == 401:
            self.__auth()
            # Try the request again
            res = self.client.post(url, **kwargs)

        return res

    def put(self, *args, **kwargs) -> object:
        """Perform a PUT request.

        Convenience wrapper for redfish.redfish_client.post that handles
        re-authentication.

        Returns:
            returns a rest request with method 'Put'
        """
        res = self.client.put(*args, **kwargs)

        # The session probably timed out. Need to re-authenticate.
        if res.status_code == 401:
            self.__auth()
            # Try the request again
            res = self.client.put(*args, **kwargs)

        return res

    def get_system_list(self) -> list:
        """Gets list of Redfish systems

        Returns:
            List of available Redfish system IDs.
        """
        systems = []
        uri = f'{self.prefix}/Systems?$expand=.'
        response = self.get(uri)
        for i in response.json().get('Members', []):
            system_id = i.get('Id') or i.get('@odata.id')
            if system_id:
                systems.append(system_id)

        return systems

    def get_chassis_list(self) -> list:
        """Gets list of Redfish chassis.

        Returns:
            List of available Redfish chassis IDs.
        """
        chassis = []
        uri = f'{self.prefix}/Chassis?$expand=.'
        response = self.get(uri)
        for i in response.json().get('Members', []):
            chassis_id = i.get('Name')
            if chassis_id:
                chassis.append(chassis_id)

        return chassis

    def get_system_reset_types(self, system: str) -> list:
        """ Get available reset actions for the system.

        Args:
            system: System string (i.e. 'System_0').

        Returns:
            List of allowable reset types.
        """
        actions = []
        uri = f'{self.prefix}/Systems/{system}/ResetActionInfo'
        response = self.get(uri)

        for i in response.json().get('Parameters', []):
            # Extra condition to make sure we are actually getting
            # the data we think we're getting. Don't trust anything.
            if i.get('Name') == 'ResetType':
                actions = i.get('AllowableValues', [])
                break

        return actions

    def reset_system(self, system: str, reset_type: str) -> bool:
        """Performs a system reset from RedFish.

        Args:
            system: System string of redfish member.
            reset_type: Reset type as string.

        Returns:
            Boolean indicating success as determined from the response
                object..
        """
        uri = f'{self.prefix}/Systems/{system}/Actions/ComputerSystem.Reset'
        body = {"ResetType": reset_type}

        response = self.post(uri, json=body)

        status = False
        if response.status_code == 204:
            # Assuming the 204 status indicates success.
            status = True
        else:
            info = response.json().get('@Message.ExtendedInfo', [])
            for i in info:
                if 'success' in i.get('MessageId', "").lower():
                    status = True
                    break

        return status


    def update_bios(self, path: str) -> bool:
        """Flash bios over redfish.

        After uploading the file for flash, will wait for
        the task to complete.

        Args:
            path: File path to upload

        Returns:
            Boolean indicating whether or not the flash succeeded.
        """
        # Get proper chassis component id for flashing.
        uri = f'{self.prefix}/UpdateService/update-multipart'
        # Get each chassis component and find the correct one
        # to update.
        chassis = None
        res = self.get(f'{self.prefix}/Chassis?$expand=.')
        for i in res.json().get('Members', []):
            if i.get('ChassisType', '') == 'Zone':
                chassis = i.get('Id')
                break

        if not chassis:
            pass
        elif not os.path.exists(path):
            pass
        else:
            parameters = {
                'Targets': [f"{self.prefix}/Chassis/{chassis}"],
                "ForceUpdate": True,
            }
            with open(path, 'rb') as f:
                files = {
                    "UpdateParameters": (
                        None,
                        json.dumps(parameters),
                        'application/json'
                    ),
                    "UpdateFile": (
                        os.path.basename(path),
                        f,
                        "application/octet-stream"
                    ),
                }
            res = requests.post(
                f'https://{self.__hostname}{uri}',
                files=files,
                auth=(self.__username, self.__password),
                verify=False
            )
            # Expects a response with the 'TaskState' of 'Running'
            # otherwise we don't step into the loop.
            res.dict = json.loads(res.text)
            task_id = res.json().get('Id')
            task_uri = f"{self.prefix}/TaskService/Tasks/{task_id}"
            while all([
                res.json().get('PercentComplete', 0) < 100,
                res.json().get('TaskState', '').lower() == 'running',
            ]):
                # The task is not done so we'll wait and check on it.
                time.sleep(30)
                res = self.get(task_uri)

            if all([
                res.json().get('PercentComplete', 0) == 100,
                res.json().get('TaskState', '').lower() == 'completed',
                res.json().get('TaskStatus', '').lower() == 'ok',
            ]):
                return True

        return False

    def clear_post_codes(self, system: str) -> bool:
        """Clears the system post code service logs.

        Args:
            system: System string of redfish member.

        Returns:
            Boolean indicating whether or not the logs were cleared
            as indicated by the response.
        """
        uri = f'{self.prefix}/Systems/{system}/' + \
            'LogServices/PostCodes/Actions/LogService.ClearLog'

        response = self.post(uri)

        status = False
        if response.status_code == 204:
            # Assuming the 204 status indicates success.
            status = True
        else:
            info = response.json().get('@Message.ExtendedInfo', [])
            for i in info:
                if 'success' in i.get('MessageId', "").lower():
                    status = True
                    break

        return status

    def get_post_codes(self, system: str) -> list:
        """Gets a list of post codes from the post code service logs.

        Args:
            system: System string of Redfish member.

        Returns:
            List of post codes from the system service log.
        """
        uri = f'{self.prefix}/Systems/{system}/LogServices/PostCodes/' + \
            'Entries'

        response = self.get(uri)

        post_codes = []
        if response.status_code == 200:
            entry_list = response.json().get("Members", [])
        elif response.status_code == 204:
            entry_list = []
        else:
            # No content which might not contain JSON.
            entry_list = []
            post_codes = None

        # Compile for performance.
        code_match = re.compile(r'POST Code[:\s]+(\w+)\b')
        for i in entry_list:
            message = i.get('Message')
            code = re.findall(code_match, message)
            code = code and code[0] or None

            if code is not None:
                post_codes.append(code)

        return post_codes
