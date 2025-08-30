import logging
import unittest
from unittest.mock import patch

from requests.exceptions import ConnectionError, ReadTimeout

from redfish_client import RedFish

logging.disable(level='ERROR')


class MockResponse(object):
    mock_json = None
    status_code = None

    def json(self):
        return self.mock_json


class TestRedFish(unittest.TestCase):

    @patch('redfish_client.requests', autospec=True)
    def test_system_list_with_members(self, mock_requests):
        res = MockResponse()
        res.status_code = 200
        res.mock_json = {
            'Members': [
                {'Id': '0'},
                {'Id': '1'},
                {'Id': '2'},
            ]
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        systems = rf.get_system_list()

        mock_client.get.assert_called_once()
        assert systems == ['0', '1', '2']

    @patch('redfish_client.requests', autospec=True)
    def test_system_list_no_members(self, mock_requests):
        res = MockResponse()
        res.status_code = 200
        res.mock_json = {
            'Members': []
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        systems = rf.get_system_list()

        mock_client.get.assert_called_once()
        assert systems == []

    @patch('redfish_client.requests', autospec=True)
    def test_get_resets_with_types(self, mock_requests):
        res = MockResponse()
        res.status_code = 200
        res.mock_json = {
            'Parameters': [{
                'AllowableValues': ['On', 'ForceOff', 'ForceOn'],
                'Name': 'ResetType',
            }]
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        resets = rf.get_system_reset_types('0')

        mock_client.get.assert_called_once()
        assert resets == ['On', 'ForceOff', 'ForceOn']

    @patch('redfish_client.requests', autospec=True)
    def test_get_resets_no_types(self, mock_requests):
        res = MockResponse()
        res.status_code = 200

        res.mock_json = {
            'Parameters': []
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        resets = rf.get_system_reset_types('0')

        mock_client.get.assert_called_once()
        assert resets == []

    @patch('redfish_client.requests', autospec=True)
    def test_reset_system_pass(self, mock_requests):
        res = MockResponse()
        res.status_code = 200
        res.mock_json = {
            '@Message.ExtendedInfo': [
                {'MessageId': 'Base.V1.Success'}
            ]
        }

        mock_client = mock_requests.Session.return_value
        mock_client.post.return_value = res

        rf = RedFish('123', 'user', 'password')
        status = rf.reset_system('0', 'On')

        mock_client.post.assert_called_once()
        assert status is True

    @patch('redfish_client.requests', autospec=True)
    def test_reset_system_fail(self, mock_requests):
        res = MockResponse()
        res.status_code = 200
        res.mock_json = {
            '@Message.ExtendedInfo': []
        }

        mock_client = mock_requests.Session.return_value
        mock_client.post.return_value = res

        rf = RedFish('123', 'user', 'password')
        status = rf.reset_system('0', 'On')

        mock_client.post.assert_called_once()
        assert status is False

    @patch('redfish_client.requests', autospec=True)
    def test_system_get_boot_opts(self, mock_requests):
        res_0 = MockResponse()
        res_1 = MockResponse()

        res_0.status_code = 200
        res_0.mock_json = {
            "Members": [
                {
                    "@odata.id": "/foo/bar/Boot0001"
                },
            ]
        }
        res_1.status_code = 200
        res_1.mock_json = {
            "DisplayName": "first boot",
            "Id": "Boot0001",
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.side_effect = [res_0, res_1]

        rf = RedFish('123', 'user', 'password')
        boot_options = rf.get_system_boot_options('0')

        mock_client.get.assert_called()
        assert boot_options == [('Boot0001', 'first boot')]

    @patch('redfish_client.requests', autospec=True)
    def test_get_boot_no_opts(self, mock_requests):
        res_0 = MockResponse()

        res_0.status_code = 200
        res_0.mock_json = {
            "Members": []
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.side_effect = [res_0]

        rf = RedFish('123', 'user', 'password')
        boot_options = rf.get_system_boot_options('0')

        mock_client.get.assert_called_once()
        assert boot_options == []

    @patch('redfish_client.requests', autospec=True)
    def test_get_post_codes(self, mock_requests):
        res_0 = MockResponse()

        res_0.status_code = 200
        res_0.mock_json = {
            "Members": [
                {"Message": "Biz: Baz; POST Code: 0x123; Foo: Bar"}
            ]
        }

        mock_client = mock_requests.Session.return_value
        mock_client.get.side_effect = [res_0]

        rf = RedFish('123', 'user', 'password')
        post_codes = rf.get_post_codes('0')

        mock_client.get.assert_called_once()
        assert post_codes == ['0x123']

    @patch('redfish_client.requests', autospec=True)
    def test_get_post_codes_404(self, mock_requests):
        res_0 = MockResponse()

        res_0.status_code = 404
        res_0.mock_json = {}

        mock_client = mock_requests.Session.return_value
        mock_client.get.side_effect = [res_0]

        rf = RedFish('123', 'user', 'password')
        post_codes = rf.get_post_codes('0')

        mock_client.get.assert_called_once()
        assert post_codes is None

    @patch('redfish_client.requests', autospec=True)
    def test_get_post_codes_204(self, mock_requests):
        res_0 = MockResponse()

        res_0.status_code = 204
        res_0.mock_json = {}

        mock_client = mock_requests.Session.return_value
        mock_client.get.side_effect = [res_0]

        rf = RedFish('123', 'user', 'password')
        post_codes = rf.get_post_codes('0')

        mock_client.get.assert_called_once()
        assert post_codes == []


class TestRedFishExceptions(unittest.TestCase):

    @patch('redfish_client.requests', autospec=True)
    def test_connectionerror_catch(self, mock_requests):
        mock_json = {'foo': 'bar'}

        mock_res = MockResponse()
        mock_res.status_code = 200
        mock_res.mock_json = mock_json

        mock_client = mock_requests.Session.return_value
        mock_client.get.side_effect = [
            ConnectionError('Connection aborted', FileNotFoundError('File not found')),
            mock_res,
        ]

        rf = RedFish('123', 'user', 'password')
        res = rf.get('/mock/endpoint')

        assert mock_client.get.call_count == 2
        assert res.json() == mock_json

    @patch('redfish_client.requests', autospec=True)
    def test_readtimeout_catch(self, mock_requests):
        mock_client = mock_requests.Session.return_value
        mock_client.get.__name__ = 'get'
        mock_client.get.side_effect = [ReadTimeout('error')]

        rf = RedFish('123', 'user', 'password')
        res = rf.get('/mock/endpoint')

        mock_client.get.assert_called()
        # Call json() method just to check that the custom response
        # doesn't break
        assert not res.ok
        assert res.json()
        assert res.status_code == 599
