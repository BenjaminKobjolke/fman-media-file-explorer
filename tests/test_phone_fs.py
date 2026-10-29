import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from io import UnsupportedOperation

from media_file_explorer.companion_link import CompanionLink, Phone
from media_file_explorer.phone_fs import PhoneFileSystem
from media_file_explorer.companion_http import PinnedHttpsClient


class PhoneFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.link = MagicMock(spec=CompanionLink)
        self.phone = Phone('id', 'Pixel', '127.0.0.1', 47611, 'token', 'a' * 64)
        self.link.peers.return_value = [self.phone]
        self.fs = PhoneFileSystem(self.link)
        self.client = MagicMock(spec=PinnedHttpsClient)
        self.client.get_json.return_value = {
            'entries': [
                {
                    'name': 'a.jpg',
                    'isDirectory': False,
                    'size': 1,
                    'modified': 1577836800000,
                }
            ]
        }
        self.fs._phones['Pixel'] = self.phone
        self.fs._clients['Pixel'] = self.client

    def test_api_path_mapping_and_nested_list(self):
        self.client.get_json.return_value = {
            'entries': [
                {
                    'name': 'DCIM',
                    'isDirectory': True,
                    'size': 0,
                    'modified': 0,
                }
            ]
        }
        self.assertEqual(self.fs._api_path('Pixel/Pictures/DCIM'), '/Pictures/DCIM')
        self.assertEqual(list(self.fs.iterdir('Pixel/Pictures')), ['DCIM'])
        self.client.get_json.assert_called_with('/v1/list', {'path': '/Pictures'})

    def test_root_phone_and_share_listings(self):
        self.client.get_json.return_value = {
            'entries': [
                {
                    'name': 'Pictures',
                    'isDirectory': True,
                    'size': 0,
                    'modified': 0,
                }
            ]
        }
        self.assertEqual(list(self.fs.iterdir('')), ['Pixel'])
        self.assertEqual(list(self.fs.iterdir('Pixel')), ['Pictures'])
        self.assertEqual(list(self.fs.iterdir('Pixel/Pictures')), ['Pictures'])

    def test_size_and_modified_use_parent_listing(self):
        self.client.get_json.return_value = {
            'entries': [
                {
                    'name': 'a.jpg',
                    'isDirectory': False,
                    'size': 12,
                    'modified': 1577836800000,
                }
            ]
        }
        self.assertEqual(self.fs.size_bytes('Pixel/Pictures/a.jpg'), 12)
        self.assertEqual(
            self.fs.modified_datetime('Pixel/Pictures/a.jpg').timestamp(),
            1577836800,
        )
        self.client.get_json.assert_called_once()

    def test_unknown_phone_is_missing(self):
        self.link.peers.return_value = []
        with self.assertRaises(FileNotFoundError):
            self.fs.is_dir('Missing')

    def test_mkdir_share_root_and_trash_unsupported(self):
        with self.assertRaises(UnsupportedOperation):
            self.fs.mkdir('Pixel/Pictures')
        with self.assertRaises(UnsupportedOperation):
            self.fs.prepare_trash('Pixel/Pictures/a.jpg')

    def test_prepare_copy_scheme_pairs(self):
        with self.assertRaises(UnsupportedOperation):
            self.fs.prepare_copy('phone://Pixel/Pictures/a.jpg', 'phone://Pixel/Pictures/b.jpg')
        tasks = self.fs.prepare_copy('phone://Pixel/Pictures/a.jpg', 'file:///tmp/a.jpg')
        self.assertEqual(len(tasks), 2)
        local_file = Path(__file__).resolve().as_uri()
        tasks = self.fs.prepare_copy(local_file, 'phone://Pixel/Pictures/a.jpg')
        self.assertEqual(len(tasks), 2)

    def test_move_same_share_renames_and_cross_scheme_copies_then_deletes(self):
        same = self.fs.prepare_move('phone://Pixel/Pictures/a.jpg', 'phone://Pixel/Pictures/b.jpg')
        self.assertEqual(len(same), 1)
        different = self.fs.prepare_move('phone://Pixel/Pictures/a.jpg', 'file:///tmp/a.jpg')
        self.assertGreaterEqual(len(different), 2)


class CompanionLinkTests(unittest.TestCase):
    @patch('media_file_explorer.companion_link.save_json')
    @patch('media_file_explorer.companion_link.load_json', return_value={})
    def test_first_contact_persists_token_and_fingerprint(self, _load, save):
        link = CompanionLink()
        with patch.object(link, '_request_approval', return_value=('token', 'b' * 64)):
            link._ensure_approved()
        self.assertEqual(link.settings['client_token'], 'token')
        self.assertEqual(link.settings['companion_fingerprint'], 'b' * 64)
        save.assert_called()

    def test_peer_cache_is_reused(self):
        link = CompanionLink()
        link.settings['client_token'] = 'token'
        with patch.object(link, '_fetch_peers', return_value=[]) as fetch:
            link.peers()
            link.peers()
        fetch.assert_called_once()


if __name__ == '__main__':
    unittest.main()
