import unittest
from unittest.mock import patch

import redfish

from redfish_clients import RedFish


class MockResponse(object):
    dict = None


class TestRedFish(unittest.TestCase):

    def test_correct_redfish(self):
        assert hasattr(redfish, 'redfish_client')

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_system_list_with_members(self, mock_redfish):
        res = MockResponse()
        res.status = 200
        res.dict = {
            'Members': [
                {'@odata.id': '/redfish/v1/Systems/0'},
                {'@odata.id': '/redfish/v1/Systems/1'},
                {'@odata.id': '/redfish/v1/Systems/2'},
            ]
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        systems = rf.get_system_list()

        mock_client.get.assert_called_once()
        assert systems == ['0', '1', '2']

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_system_list_no_members(self, mock_redfish):
        res = MockResponse()
        res.status = 200
        res.dict = {'Members': []}

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        systems = rf.get_system_list()

        mock_client.get.assert_called_once()
        assert systems == []

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_get_resets_with_types(self, mock_redfish):
        res = MockResponse()
        res.status = 200
        res.dict = {
            'Parameters': [{
                'AllowableValues': ['On', 'ForceOff', 'ForceOn'],
                'Name': 'ResetType',
            }]
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        resets = rf.get_system_reset_types('0')

        mock_client.get.assert_called_once()
        assert resets == ['On', 'ForceOff', 'ForceOn']

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_get_resets_no_types(self, mock_redfish):
        res = MockResponse()
        res.status = 200

        res.dict = {
            'Parameters': []
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.get.return_value = res

        rf = RedFish('123', 'user', 'password')
        resets = rf.get_system_reset_types('0')

        mock_client.get.assert_called_once()
        assert resets == []

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_reset_system_pass(self, mock_redfish):
        res = MockResponse()
        res.status = 200
        res.dict = {
            '@Message.ExtendedInfo': [
                {'MessageId': 'Base.V1.Success'}
            ]
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.post.return_value = res

        rf = RedFish('123', 'user', 'password')
        status = rf.reset_system('0', 'On')

        mock_client.post.assert_called_once()
        assert status is True

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_reset_system_fail(self, mock_redfish):
        res = MockResponse()
        res.status = 200
        res.dict = {
            '@Message.ExtendedInfo': []
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.post.return_value = res

        rf = RedFish('123', 'user', 'password')
        status = rf.reset_system('0', 'On')

        mock_client.post.assert_called_once()
        assert status is False

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_get_boot_opts(self, mock_redfish):
        res_0 = MockResponse()
        res_1 = MockResponse()

        res_0.status = 200
        res_0.dict = {
            "Members": [
                {
                    "@odata.id": "/foo/bar/Boot0001"
                },
            ]
        }
        res_1.status = 200
        res_1.dict = {
            "DisplayName": "first boot",
            "Id": "Boot0001",
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.get.side_effect = [res_0, res_1]

        rf = RedFish('123', 'user', 'password')
        boot_options = rf.get_boot_options('0')

        mock_client.get.assert_called()
        assert boot_options == [('Boot0001', 'first boot')]

    @patch('lib.remix.redfish_helpers.redfish', autospec=True)
    def test_get_boot_no_opts(self, mock_redfish):
        res_0 = MockResponse()

        res_0.status = 200
        res_0.dict = {
            "Members": []
        }

        mock_client = mock_redfish.redfish_client.return_value
        mock_client.get.side_effect = [res_0]

        rf = RedFish('123', 'user', 'password')
        boot_options = rf.get_boot_options('0')

        mock_client.get.assert_called_once()
        assert boot_options == []


if __name__ == '__main__':
    unittest.main()
