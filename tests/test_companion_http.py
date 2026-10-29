import unittest
from unittest.mock import patch

from media_file_explorer.companion_http import PinnedHttpsClient


class HttpMappingTests(unittest.TestCase):
    def test_status_codes_map_to_os_errors(self):
        client = PinnedHttpsClient('localhost', 1, '0' * 64)
        for status, error in (
            (404, FileNotFoundError),
            (409, FileExistsError),
            (401, PermissionError),
            (403, PermissionError),
            (500, OSError),
        ):
            with self.subTest(status=status), patch.object(
                client, '_request', side_effect=error('mapped')
            ):
                with self.assertRaises(error):
                    client.get_json('/v1/list', {})


if __name__ == '__main__':
    unittest.main()
