import os
import time
import json

import redfish
import requests


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
    ) -> None:
        """Initializes the Redfish client connection.

        Args:
            hostname: Redfish host ip address (i.e. BMC).
            username: Redfish user (i.e. BMC).
            password: Redfish password (i.e. BMC).
        """

        # Store values for later so we can reconnect automatically if needed.
        self.__hostname = hostname
        self.__username = username
        self.__password = password

        self.prefix = '/redfish/v1'
        self.__auth()

    def __auth(self) -> None:
        """Establishes client Redfish connection.

        """
        self.client = redfish.redfish_client(
            base_url=f'https://{self.__hostname}',
            username=self.__username,
            password=self.__password,
            default_prefix=self.prefix
        )
        self.client.login(auth='session')

    def get(self, *args, **kwargs) -> object:
        """Perform a GET request.

        Convenience wrapper for redfish.redfish_client.get that handles
        re-authentication.

        Returns:
            returns a rest request with method 'Get'
        """
        res = self.client.get(*args, **kwargs)

        # The session probably timed out. Need to re-authenticate.
        if res.status == 401:
            self.__auth()
            # Try the request again
            res = self.client.get(*args, **kwargs)

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
        if res.status == 401:
            self.__auth()
            # Try the request again
            res = self.client.patch(*args, **kwargs)

        return res

    def post(self, *args, **kwargs) -> object:
        """Perform a POST request.

        Convenience wrapper for redfish.redfish_client.post that handles
        re-authentication.

        Returns:
            returns a rest request with method 'Post'
        """
        res = self.client.post(*args, **kwargs)

        # The session probably timed out. Need to re-authenticate.
        if res.status == 401:
            self.__auth()
            # Try the request again
            res = self.client.post(*args, **kwargs)

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
        if res.status == 401:
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
        for i in response.dict.get('Members', []):
            system_id = i.get('Id')
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
        for i in response.dict.get('Members', []):
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

        for i in response.dict.get('Parameters', []):
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

        response = self.post(uri, body=body)
        info = response.dict.get('@Message.ExtendedInfo', [])

        for i in info:
            if 'success' in i.get('MessageId', "").lower():
                return True

        return False

    def get_boot_options(self, system: str) -> list:
        """Gets the system boot menu options.

        Not to be confused with get_boot_order() which only returns
        the current boot order.

        Args:
            system: System string of redfish member.

        Returns:
            List of tuples containing the id and name of each boot
            option respectively.
        """
        boot_options = []
        uri = f'{self.prefix}/Systems/{system}/BootOptions'

        response = self.get(uri)

        members = response.dict.get('Members', [])

        for i in members:
            # Every boot option has a uri with extra info.
            uri = i.get('@odata.id')
            # Make a new request to get the name and id.
            r = self.get(uri)

            boot_id = r.dict.get('Id', '')
            boot_name = r.dict.get('DisplayName', '')

            # Append the id and name as a tuple.
            # Most applications probably only care for these 2 anyway
            boot_options.append((boot_id, boot_name))

        return boot_options

    def get_boot_order(self, system: str) -> list:
        """Gets the system menu boot order.

        Not to be confused with get_boot_options() which returns all
        available boot menu option. The order may not match the actual
        boot order.

        This is often useful, in combination with get_boot_options(),
        for setting a specific boot order.

        Args:
            system: System string of redfish member.

        Returns:
            List of boot option id corresponding to the system boot
            priority.
        """
        uri = f'{self.prefix}/Systems/{system}'

        response = self.get(uri)

        boot = response.dict.get('Boot', {})
        boot_order = boot.get('BootOrder', [])

        return boot_order

    def set_boot_order(self, system: str, order: list) -> bool:
        """Set the system boot order.

        https://docs.nvidia.com/networking/display/bluefieldbmcv2309/boot+order+configuration

        Args:
            system: System string of redfish member.
            order: List of boot options. These can be determined by
                get_boot_order()

        Returns:
            A boolean indicating whether or not the boot order change
                was set, as determined by checking pending settings.
                The pending boot order should match the provided order.

        """
        uri = f'{self.prefix}/Systems/{system}/Settings'
        body = {'Boot': {'BootOrder': [*order]}}

        # 204 (no content) is expected so no need to check response
        self.patch(uri, body=body)

        # Check that the order is properly set.
        response = self.get(uri)

        boot = response.dict.get('Boot', {})
        pending_order = boot.get('BootOrder', [])

        if pending_order == order:
            return True

        return False

    def update_bios(self, path: str) -> bool:
        """Update bios over redfish.

        This may be used to update other firmware.
        https://developer.dell.com/apis/2978/versions/7.xx/docs/Tasks/1MultipartUpdates.md

        After uploading the file for flash, will wait for
        the task to complete.

        Args:
            path: File path to upload.

        Returns:
            Boolean indicating whether or not the flash succeeded.
        """
        # Get proper chassis component id for flashing.
        uri = f'{self.prefix}/UpdateService/update-multipart'
        # Get each chassis component and find the correct one
        # to update.
        chassis = None
        res = self.get(f'{self.prefix}/Chassis?$expand=.')
        for i in res.dict.get('Members', []):
            # TODO: Is this always true? Multiple Zones?
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
            files = {
                "UpdateParameters": (
                    None,
                    json.dumps(parameters),
                    'application/json'
                ),
                "UpdateFile": (
                    os.path.basename(path),
                    open(path, 'rb'),
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
            task_id = res.dict.get('Id')
            task_uri = f"{self.prefix}/TaskService/Tasks/{task_id}"
            while all([
                res.dict.get('PercentComplete', 0) < 100,
                res.dict.get('TaskState', '').lower() == 'running',
            ]):
                # The task is not done so we'll wait and check on it.
                time.sleep(30)
                res = self.get(task_uri)

            if all([
                res.dict.get('PercentComplete', 0) == 100,
                res.dict.get('TaskState', '').lower() == 'completed',
                res.dict.get('TaskStatus', '').lower() == 'ok',
            ]):
                return True

        return False
