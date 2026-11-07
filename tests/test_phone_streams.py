import io
import os
import unittest
from io import UnsupportedOperation
from pathlib import Path
from unittest.mock import MagicMock

from media_file_explorer.companion_link import CompanionLink, Phone
from media_file_explorer.companion_http import PinnedHttpsClient
from media_file_explorer.phone_fs import PhoneFileSystem


class PhoneStreamTests(unittest.TestCase):
    def setUp(self):
        self.link = MagicMock(spec=CompanionLink)
        self.phone = Phone('id', 'Pixel', '127.0.0.1', 47611, 'token', 'a' * 64)
        self.link.peers.return_value = [self.phone]
        self.fs = PhoneFileSystem(self.link)
        self.client = MagicMock(spec=PinnedHttpsClient)
        self.entries = [
            {'name': 'a.jpg', 'isDirectory': False, 'size': 3},
            {'name': 'DCIM', 'isDirectory': True, 'size': 0},
        ]
        self.client.get_json.side_effect = self._listing
        self.fs._phones['Pixel'] = self.phone
        self.fs._clients['Pixel'] = self.client

    def _listing(self, _route, params):
        if params['path'] == '/':
            return {'entries': [{'name': 'Pictures', 'isDirectory': True}]}
        return {'entries': self.entries}

    def test_read_stream_is_returned_and_context_managed(self):
        stream = io.BytesIO(b'data')
        self.client.open_file.return_value = stream

        with self.fs.open('Pixel/Pictures/a.jpg', 'rb') as result:
            self.assertIs(result, stream)
            self.assertEqual(result.read(2), b'da')

        self.client.open_file.assert_called_once_with('/Pictures/a.jpg')
        self.assertTrue(stream.closed)

    def test_read_rejects_missing_and_directories_without_opening_stream(self):
        for path, expected in [
            ('Pixel/Pictures/missing.jpg', FileNotFoundError),
            ('Pixel/Pictures/DCIM', IsADirectoryError),
            ('Pixel/Pictures', IsADirectoryError),
            ('Pixel', IsADirectoryError),
        ]:
            with self.subTest(path=path):
                with self.assertRaises(expected):
                    self.fs.open(path, 'rb')

        self.client.open_file.assert_not_called()

    def test_unsupported_modes_are_rejected(self):
        for mode in ('r', 'w', 'ab', 'rb+'):
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    self.fs.open('Pixel/Pictures/a.jpg', mode)

    def test_write_stages_then_uploads_and_invalidates_listing(self):
        uploaded = []

        def capture_upload(local_path, api_path, *_args):
            uploaded.append((Path(local_path).read_bytes(), api_path, local_path))

        self.client.upload.side_effect = capture_upload
        with self.fs.open('Pixel/Pictures/new.jpg', 'wb') as stream:
            stream.write(b'abc')

        self.assertEqual(len(uploaded), 1)
        contents, api_path, local_path = uploaded[0]
        self.assertEqual((contents, api_path), (b'abc', '/Pictures/new.jpg'))
        self.assertFalse(os.path.exists(local_path))

        self.entries = [{'name': 'new.jpg', 'isDirectory': False}]
        self.assertTrue(self.fs.exists('Pixel/Pictures/new.jpg'))
        self.assertEqual(self.client.get_json.call_count, 3)

    def test_exception_discards_staged_write(self):
        local_paths = []
        with self.assertRaisesRegex(RuntimeError, 'cancelled'):
            with self.fs.open('Pixel/Pictures/new.jpg', 'wb') as stream:
                local_paths.append(stream.name)
                stream.write(b'partial')
                raise RuntimeError('cancelled')

        self.client.upload.assert_not_called()
        self.assertFalse(os.path.exists(local_paths[0]))

    def test_plain_close_uploads_once(self):
        uploaded = []
        self.client.upload.side_effect = lambda local, remote, *_: uploaded.append(
            (Path(local).read_bytes(), remote)
        )
        stream = self.fs.open('Pixel/Pictures/new.jpg', 'wb')
        stream.write(b'abc')
        stream.close()
        stream.close()

        self.assertEqual(uploaded, [(b'abc', '/Pictures/new.jpg')])
        self.assertEqual(self.client.upload.call_count, 1)

    def test_write_rejects_roots_directories_and_missing_parents(self):
        for path, expected in [
            ('Pixel', UnsupportedOperation),
            ('Pixel/Pictures', UnsupportedOperation),
            ('Pixel/Pictures/DCIM', IsADirectoryError),
            ('Pixel/Pictures/nope/new.jpg', FileNotFoundError),
        ]:
            with self.subTest(path=path):
                with self.assertRaises(expected):
                    self.fs.open(path, 'wb')

        self.client.upload.assert_not_called()

    def test_mkdir_existing_folder_raises_without_post(self):
        with self.assertRaises(FileExistsError):
            self.fs.mkdir('Pixel/Pictures/DCIM')

        self.client.post_json.assert_not_called()


if __name__ == '__main__':
    unittest.main()
