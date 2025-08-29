from http.client import RemoteDisconnected
import json
import logging
import os
import re
import time
import urllib3

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, ReadTimeout
from requests.models import Response
from requests.packages.urllib3.util.retry import Retry


class ValidationError(Exception):
    pass


class RedFish:
    """Redfish client wrapper.

    Convenience wrapper for Redfish to extend and define common methods
    for managing a Redfish connection.

    Attributes:
        client: Refish client object.
        default_prefix: Redfish API endpoint root.
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

        logging.getLogger('requests').setLevel(logging.ERROR)
        logging.getLogger('urllib3').setLevel(logging.ERROR)
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Store values for later so we can reconnect automatically if needed.
        self.__hostname = hostname
        self.__username = username
        self.__password = password
        self.__port = port

        self.prefix = '/redfish/v1'
        self.base_url = f'https://{self.__hostname}:{self.__port}'

        self.__auth()

    @property
    def __readtimeout_response(self) -> object:
        """Make a response object for requests that timeout.

        Returns:
            Response object with empty values.
        """
        res_code = 599
        res_json = {
            "status": "CLIENT_TIMEOUT",
            "code": res_code,
            "error": "ReadTimeout",
            "message": "Client timed out while waiting for server response.",
            "retryable": True
        }

        empty_response = Response()
        empty_response.status_code = res_code
        empty_response._content = json.dumps(res_json).encode('utf-8')

        return empty_response

    @property
    def default_update_target(self):
        """Get the default update component.

        This will often be the chassis component of type 'zone'
        which may manage the firmware update for any relevant components
        specifically targeted by the firmware package.

        Returns:
            String containing the Id of the chassis zone.
        """
        # TODO: Does this work the way I think it does (managing where
        #   to send the update)?
        endpoint = f'{self.prefix}/Chassis?$expand=.'
        res = self.get(endpoint)
        # Get each chassis component and find the correct one.
        # The general chassis component ('ChassisType': 'Zone')
        # will be used as the general update target for the system.
        target = None
        for i in res.json().get('Members', []):
            if i.get('ChassisType', '').lower() == 'zone':
                target = i.get('@odata.id')
                break

        # If we don't have a chassis Zone, default to BMC.
        target = target or self.get_update_targets(
            attribute_list=[{'Id': 'BMC'}, {'ManagerType': 'BMC'}]
        )

        return target

    def __auth(self) -> None:
        """Establishes client Redfish connection.
        """
        self.client = requests.Session()
        self.client.verify = False
        self.client.auth = (self.__username, self.__password)

        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[408, 500]
        )
        # Builtin retry mechanism
        self.client.mount('https://', HTTPAdapter(max_retries=retries))
        self.client.mount('http://', HTTPAdapter(max_retries=retries))

    def __reauth(method):  # noqa: E0213 pylint: disable=no-self-argument
        """Re-authentication wrapper for request methods.

        Args:
            method: Callable HTTP method object (e.g. self.post).

        Returns:
            Wrapped method with automatic re-authentication.
        """
        def wrapper(self, url, **kwargs):
            res = method(self, url, **kwargs)  # noqa: E1102 pylint: disable=not-callable

            if res.status_code == 401:
                # Session timed out. Need to re-authenticate.
                self.__auth()
                # Try the request again
                res = method(self, url, **kwargs)  # noqa: E1102 pylint: disable=not-callable

            return res

        return wrapper

    def __retry(method):  # noqa: 213 pylint: disable=no-self-argument
        """Retry HTTP request for recoverable exceptions.

        This method wraps a standard HTTP request (e.g., GET, POST),
        retrying on specific exceptions (and session reinitialization)
        if necessary. It is designed to handle intermittent failures
        and to ensure consistent behavior across all HTTP verbs.

        Args:
            method: Callable HTTP method from the requests.Session
                object (e.g. self.client.post).

        Returns:
            Response object from the HTTP request.

        Raises:
            Re-raises any unhandled exceptions after retry attempts are
            exhausted.
        """
        def wrapper(self, url, **kwargs):
            logger = logging.getLogger(__name__)

            try:
                res = method(self, url, **kwargs)  # noqa: E1102 pylint: disable=not-callable
            except RemoteDisconnected as e:
                # Host intermittently disconnected for some reason so retry
                # and warn.
                logger.warning(e)
                res = method(self, url, **kwargs)  # noqa: E1102 pylint: disable=not-callable
            except ConnectionError as e:
                # Intermittent ConnectionError exceptions during ssl
                # handshake possibly related to low level requests library
                # bug https://github.com/psf/requests/issues/3829 but the
                # issue persists both with explicit `verify=False` for each
                # request and when using special Session() decorators to
                # override SSL cert envvars. Since this doesn't occur
                # frequently, catching and refreshing the Session before
                # retry should address most cases.
                logger.error(e)
                self.__auth()
                res = method(self, url, **kwargs)  # noqa: E1102 pylint: disable=not-callable
            except ReadTimeout:
                # Timeout waiting for a response. Return an
                # appropriate response and move on to avoid
                # breaking dependent code on edge-cases.
                res = self.__readtimeout_response

            return res

        return wrapper

    def __get_inventory(self, endpoint):
        """Generic method for getting inventory lists

        Returns:
            List of tuples containing the component Id and endpoint.
        """
        res = self.get(endpoint)

        inventory = []
        for i in res.json().get('Members', []):
            mem_id = i.get('Id')
            endpoint = i.get('@odata.id')

            if mem_id and endpoint:
                inventory.append((mem_id, endpoint))

        return inventory

    def __normalize_update_targets(
        self,
        target_list: list,
        ignore_exceptions: bool = False,
    ) -> list:
        """Normalize UpdateService inventory member Ids to endpoints

        This is an adapter function to handle both member Ids or
        update endpoints since both may be used depending on
        convenience but it's better to use the explicit update
        endpoint than rely on the RedFish API to perform this
        conversion itself when we attempt the update.

        Args:
            target_list (list): List containing UpdateService
                inventory member Ids, endpoints or a mix of both.

        Returns:
            List of UpdateService inventory member endpoints only.
        """
        firmware_inventory = self.get_firmware_inventory()
        software_inventory = self.get_software_inventory()
        # Combine both software and firmware inventories.
        update_inventory = [*firmware_inventory, *software_inventory]

        update_targets = []
        for i in target_list:
            if i and self.prefix in i:
                # Assumes that the user knows what endpoint they want
                # and that this is correct.
                update_targets.append(i)
                continue

            # Item is a component Id so get the matching endpoint.
            # Technically the API does Id to endpoint conversion
            # itself but will happily accept nonsense targets and
            # report back that everything is okay. We could compare with
            # the API after to validate but without doing the conversion
            # ourselves, we have no way of knowing if this is correct
            # and comparing length is only so verbose.
            is_match = False
            for mem_id, endpoint in update_inventory:
                if i == mem_id:
                    is_match = True
                    break

            if is_match:
                update_targets.append(endpoint)
            elif ignore_exceptions:
                pass
            elif not i:
                # If you're seeing this, that means the component list
                # provided contains None.
                raise ValidationError(
                    'Invalid UpdateService component',
                    f'Member cannot be {type(i)}'
                )
            else:
                # If you're seeing this, that means the component list
                # provided contains either an invalid update endpoint
                # (remember to include the /redfish/v1 prefix) or the
                # component could not be found in either software or
                # firmware inventories.
                #
                # You should double check the output of
                # get_software_inventory() and get_firmware_inventory()
                raise ValidationError(
                    'Invalid UpdateService component',
                    f"No such member '{i}'",
                )

        return update_targets

    @__retry
    @__reauth
    def get(self, url, **kwargs) -> object:
        """Perform a GET request.

        Returns:
            returns a rest request with method 'Get'
        """
        url = self.base_url + url

        return self.client.get(url, **kwargs)

    @__retry
    @__reauth
    def patch(self, url, **kwargs) -> object:
        """Perform a PATCH request.

        Returns:
            returns a rest request with method 'Patch'
        """
        url = self.base_url + url

        return self.client.patch(url, **kwargs)

    @__retry
    @__reauth
    def post(self, url, **kwargs) -> object:
        """Perform a POST request.

        Returns:
            returns a rest request with method 'Post'
        """
        url = self.base_url + url

        return self.client.post(url, **kwargs)

    @__retry
    @__reauth
    def put(self, url, **kwargs) -> object:
        """Perform a PUT request.

        Returns:
            returns a rest request with method 'Put'
        """
        url = self.base_url + url

        return self.client.put(url, **kwargs)

    def get_system_list(self) -> list:
        """Gets list of Redfish systems

        Returns:
            List of available Redfish system IDs.
        """
        systems = []
        endpoint = f'{self.prefix}/Systems?$expand=.'
        res = self.get(endpoint)
        for i in res.json().get('Members', []):
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
        endpoint = f'{self.prefix}/Chassis?$expand=.'
        res = self.get(endpoint)
        for i in res.json().get('Members', []):
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
        endpoint = f'{self.prefix}/Systems/{system}/ResetActionInfo'
        res = self.get(endpoint)

        for i in res.json().get('Parameters', []):
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
            Boolean indicating whether the system reset was successful,
            as determined by the response object.
        """
        endpoint = \
            f'{self.prefix}/Systems/{system}/Actions/ComputerSystem.Reset'
        body = {"ResetType": reset_type}

        res = self.post(endpoint, json=body)

        status = False
        if res.status_code == 204:
            # Assuming the 204 (no content) status indicates success.
            status = True
        else:
            # Explicit check.
            info = res.json().get('@Message.ExtendedInfo', [])
            for i in info:
                if 'success' in i.get('MessageId', "").lower():
                    status = True
                    break

        return status

    def get_system_boot_options(self, system: str) -> list:
        """Gets the system boot menu options.

        Not to be confused with get_system_boot_order() which only
        returns the current boot order.

        Args:
            system: System string of redfish member.

        Returns:
            List of tuples containing the id and name of each boot
            option respectively.
        """
        boot_options = []
        endpoint = f'{self.prefix}/Systems/{system}/BootOptions'

        res = self.get(endpoint)

        members = res.json().get('Members', [])

        for i in members:
            # Every boot option has a endpoint with extra info.
            endpoint = i.get('@odata.id')
            # Make a new request to get the name and id.
            res = self.get(endpoint)

            boot_id = res.json().get('Id')
            boot_name = res.json().get('DisplayName')

            # Append the id and name  as a tuple.
            # Most applications probably only care for these 2 anyway
            boot_options.append((boot_id, boot_name))

        return boot_options

    def get_system_boot_order(self, system: str) -> list:
        """Gets the system menu boot order.

        Not to be confused with get_system_boot_options() which returns
        all available boot menu option. The order may not match the
        actual boot order.

        This is often useful, in combination with get_system_boot_options(),
        for setting a specific boot order.

        Args:
            system: System string of redfish member.

        Returns:
            List of boot option id corresponding to the system boot
            priority.
        """
        endpoint = f'{self.prefix}/Systems/{system}'

        res = self.get(endpoint)

        boot = res.json().get('Boot', {})
        boot_order = boot.get('BootOrder', [])

        return boot_order

    def set_boot_order(self, system: str, order: list) -> bool:
        """Set the system boot order.

        https://docs.nvidia.com/networking/display/bluefieldbmcv2309/boot+order+configuration

        Args:
            system: System string of redfish member.
            order: List of boot options. These can be determined by
                get_system_boot_order()

        Returns:
            A boolean indicating whether or not the boot order change
            was set, as determined by checking pending settings.
            The pending boot order should match the provided order.

        """
        endpoint = f'{self.prefix}/Systems/{system}/Settings'
        body = {'Boot': {'BootOrder': [*order]}}

        # 204 (no content) is expected so no need to check response
        self.patch(endpoint, json=body)

        # Check that the order is properly set.
        res = self.get(endpoint)

        boot = res.json().get('Boot', {})
        pending_order = boot.get('BootOrder', [])

        if pending_order == order:
            return True

        return False

    def get_firmware_inventory(self):
        """Get the UpdateService firmware inventory

        Returns:
            List of tuples containing the component Id and update
            endpoint.
        """
        endpoint = f'{self.prefix}/UpdateService/FirmwareInventory?$expand=.'
        return self.__get_inventory(endpoint)

    def get_software_inventory(self):
        """Get the UpdateService software inventory

        Returns:
            List of tuples containing the component Id and update
            endpoint.
        """
        endpoint = f'{self.prefix}/UpdateService/SoftwareInventory?$expand=.'
        return self.__get_inventory(endpoint)

    def get_update_targets(
        self,
        target_list: list = [],
        attribute_list: list = [],
    ):
        """Get the normal UpdateService target endpoints.

        This will retrieve a list of UpdateService target endpoints that
        match certain criteria, either explicitly with component Ids or
        endpoints provided by target_list or implicitly based on a list
        of matching attributes

        This is needed due to variation between the component Id used by
        the UpdateService and the (more common) Id from the Chassis
        list.

        Args:
            target_list (list): List containing component Ids or
                endpoints.
            attribute_list (list): List of dictionaries containing
                key, value pairs as match critera. For each item,
                all key, value pairs must match (logical AND) while
                separate items are interpreted as logic OR fashion.

        Returns:
            List of normalized update target endpoints.
        """
        inventory_data = []
        update_targets = []

        # Get firmware inventory data.
        endpoint = f'{self.prefix}/UpdateService/FirmwareInventory?$expand=.'
        res = self.get(endpoint)
        inventory_data.extend(res.json().get('Members', []))

        # Get software inventory data.
        endpoint = f'{self.prefix}/UpdateService/SoftwareInventory?$expand=.'
        res = self.get(endpoint)
        inventory_data.extend(res.json().get('Members', []))

        # Explicit match
        related_data = {}
        for i in target_list:
            if not i:
                continue
            for member in inventory_data:
                target_endpoint = member.get('@odata.id')
                if target_endpoint in update_targets:
                    continue
                elif any([
                    member.get('Id') == i,
                    target_endpoint == i,
                ]):
                    # Target is a valid update target.
                    # No need to process further.
                    update_targets.append(target_endpoint)
                    break

                related_items = member.get('RelatedItem', [])
                for endpoint in [i.get('@odata.id') for i in related_items]:
                    if not endpoint:
                        continue
                    elif endpoint in related_data.keys():
                        # We already got this endpoint so no need to get
                        # this again.
                        res_json = related_data.get(endpoint)
                    else:
                        res = self.get(endpoint)
                        res_json = res.json()

                        related_data[endpoint] = res_json

                    # Try this again, this time using the related data.
                    if target_endpoint in update_targets:
                        continue
                    elif any([
                        res_json.get('@odata.id') == i,
                        res_json.get('Id') == i,
                    ]):
                        update_targets.append(target_endpoint)
                        break

        # Implicit match.
        for attr in attribute_list:
            if not attr:
                continue
            for member in inventory_data:
                target_endpoint = member.get('@odata.id')
                if target_endpoint in update_targets:
                    continue
                elif all([
                    member.get(k) == v for k, v in attr.items()
                ]):
                    # Attributes match.
                    update_targets.append(target_endpoint)
                    break

                related_items = member.get('RelatedItem', [])
                for endpoint in [i.get('@odata.id') for i in related_items]:
                    if not endpoint:
                        continue
                    elif endpoint in related_data.keys():
                        # We already got this endpoint so no need to get
                        # this again.
                        res_json = related_data.get(endpoint)
                    else:
                        res = self.get(endpoint)
                        res_json = res.json()

                        related_data[endpoint] = res_json

                    # Try this again, this time using the related data.
                    if target_endpoint in update_targets:
                        continue
                    elif all([
                        res_json.get(k) == v for k, v in attr.items()
                    ]):
                        # Attributes match.
                        update_targets.append(target_endpoint)
                        break

        # No match criteria so just get everything
        if not any([
            target_list,
            attribute_list,
        ]):
            for member in inventory_data:
                target_endpoint = member.get('@odata.id')
                if target_endpoint in update_targets:
                    continue
                update_targets.append(target_endpoint)

        return update_targets

    def set_update_targets(
        self,
        target_list: list,
        endpoint: str = None,
    ) -> bool:
        """Specifies which firmware component to update.

        Explicitly sets the update target prior to updating firmware.
        Although this may not be strictly necessary for all components,
        this is especially applicable for retimer updates.

        Args:
            target_list (list): List containing UpdateService
                inventory member Ids, endpoints or a mix of both.
            endpoint (str): Optional override for the default
                multipart update endpoint.

        Returns:
            Boolean indicating whether the update targets were set
            successfully.
        """
        # Use default multipart update endpoint, otherwise this
        # can be passed as an argument in case a different endpoint
        # should be used instead (such as '/UpdateService')
        update_endpoint = endpoint or \
            f'{self.prefix}/UpdateService/update-multipart'

        # Adapter method to normalize targets
        target_list = self.__normalize_update_targets(target_list)

        body = {"HttpPushUriTargets": target_list}
        res = self.patch(update_endpoint, json=body)

        if res.ok:
            # Confirmation check to make sure it actually updated.
            res = self.get(update_endpoint)

            # Expected
            target_list.sort()
            # Actual
            updated_targets = res.json().get("HttpPushUriTargets", [])
            updated_targets.sort()

            return updated_targets == target_list

        return False

    def update_firmware(
        self,
        path: str,
        endpoint=None,
        target_list=None,
        wait=True,
    ) -> bool:
        """Flash bios over redfish.

        After uploading the file for flash, will wait for
        the task to complete.

        Args:
            path: Firmware file path.
            endpoint (str): Optional override for the default
                multipart update endpoint.
            target_list (list): List containing UpdateService
                inventory member Ids, endpoints or a mix of both.
            wait (bool): If True, the method will wait for the firmware
                update process to complete before returning. If False,
                the method will initiate the firmware update and return
                immediately without waiting.

        Returns:
            Boolean indicating whether or not the flash succeeded.
        """
        # Use default multipart update endpoint, otherwise this
        # can be passed as an argument in case a different endpoint
        # should be used instead (such as '/UpdateService')
        endpoint = endpoint or \
            f'{self.prefix}/UpdateService/update-multipart'
        parameters = {
            "ForceUpdate": True,
            "Targets": [],
        }

        # TODO: Deprecate the target list. This doesn't work the way
        #   you think.
        # res = self.get(endpoint)
        # active_targets = res.json().get('HttpPushUriTargets', [])
        # # Set target list, using provided targets first otherwise
        # # falling back to the active targets before using the
        # # default update target.
        # target_list = target_list or active_targets
        # target_list = target_list or [self.default_update_target]
        # # Normalize and validate targets.
        # target_list = self.__normalize_update_targets(target_list, False)
        # # TODO: How necessary are targets?
        # # Only set the target list if we have targets. This might be
        # # necessary but if we can't
        # target_list and parameters.update({'Targets': target_list})

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
            res = self.post(endpoint, files=files)
            res_json = res.json()

        # Expects a response with the 'TaskState' of 'Running'
        # otherwise we don't step into the loop.
        # The task is not done so we'll wait and check on it.
        task_id = res_json.get('Id')
        endpoint = f"{self.prefix}/TaskService/Tasks/{task_id}"

        time_start = time.time()
        while wait and all([
            res_json.get('PercentComplete', 0) < 100,
            res_json.get('TaskState', '').lower() == 'running',
            time.time() - time_start < 1800,
        ]):
            time.sleep(30)
            try:
                res = self.get(endpoint)
                res_json = res.json()
            except Exception as e:
                # This may fail if the task endpoint becomes temporarily
                # unreachable during the initial stages of the HTTP
                # "push" multi-part firmware update and times out. This
                # can safely fail during that time with no bad effect
                # since we'll get the actual response when it starts
                # behaving normally again.
                logger = logging.getLogger(__name__)
                logger.warning(e)
                res_json = {}

        status = False
        if wait and all([
            res_json.get('PercentComplete', 0) == 100,
            res_json.get('TaskState', '').lower() == 'completed',
            res_json.get('TaskStatus', '').lower() == 'ok',
        ]):
            status = True
        elif all([
            res_json.get('TaskState', '').lower() == 'running',
            res_json.get('TaskStatus', '').lower() == 'ok',
        ]):
            # Do not wait for this to finish so assume this is
            # fine if we get this far.
            status = True

        return status

    def clear_post_codes(self, system: str) -> bool:
        """Clears the system post code service logs.

        Args:
            system: System string of redfish member.

        Returns:
            Boolean indicating whether or not the logs were cleared
            as indicated by the response.
        """
        endpoint = f'{self.prefix}/Systems/{system}/' + \
            'LogServices/PostCodes/Actions/LogService.ClearLog'

        res = self.post(endpoint)

        status = False
        if res.status_code == 204:
            # Assuming the 204 (no content) status indicates success.
            status = True
        else:
            # Explicit check.
            info = res.json().get('@Message.ExtendedInfo', [])
            for i in info:
                if 'success' in i.get('MessageId', "").lower():
                    status = True
                    break

        return status

    def get_task_list(self) -> list:
        """Get the list of task endpoints

        This is usually helpful for monitoring firmware updates by
        comparing this list before and after starting an update to
        indirectly get the active task.

        Returns:
            List of task endpoints.
        """
        task_list = []

        res = self.get(f'{self.prefix}/TaskService/Tasks')
        for i in res.json().get('Members', []):
            task = i.get('@odata.id')
            task and task_list.append(task)

        return task_list

    def get_post_codes(self, system: str) -> list:
        """Gets a list of post codes from the post code service logs.

        Args:
            system: System string of Redfish member.

        Returns:
            List of post codes from the system service log.
        """
        endpoint = f'{self.prefix}/Systems/{system}/LogServices/PostCodes/' + \
            'Entries'

        res = self.get(endpoint)

        post_codes = []
        if res.status_code == 200:
            entry_list = res.json().get("Members", [])
        elif res.status_code == 204:
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
