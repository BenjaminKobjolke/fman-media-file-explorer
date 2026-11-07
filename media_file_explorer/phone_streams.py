"""Binary stream adapters for phone files."""
import os
import posixpath
import tempfile
from io import UnsupportedOperation
from typing import TYPE_CHECKING, BinaryIO

from .phone_transfers import PhoneTransfers

if TYPE_CHECKING:
    from .phone_fs import PhoneFileSystem


READ_MODE = 'rb'
WRITE_MODE = 'wb'


def open_phone_file(fs: 'PhoneFileSystem', path: str, mode: str) -> BinaryIO:
    if mode not in (READ_MODE, WRITE_MODE):
        raise ValueError("Phone files open only in 'rb' or 'wb' mode")

    clean_path = fs._clean(path)
    if mode == READ_MODE:
        if fs.is_dir(clean_path):
            raise IsADirectoryError(path)
        parts = fs._parts(clean_path)
        return fs._client(parts[0]).open_file(fs._api_path(clean_path))

    parts = fs._parts(clean_path)
    if len(parts) < 3:
        raise UnsupportedOperation('Files can only be written inside a phone share')
    if fs.exists(clean_path) and fs.is_dir(clean_path):
        raise IsADirectoryError(path)
    parent = posixpath.dirname(clean_path)
    if not fs.exists(parent):
        raise FileNotFoundError(parent)
    return _PhoneUploadStream(PhoneTransfers(fs), clean_path)


class _PhoneUploadStream:
    """Stage a complete upload locally before sending it to the phone."""

    def __init__(self, transfers: PhoneTransfers, path: str) -> None:
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        self._temp_file = temp_file
        self._temp_name = temp_file.name
        self._transfers = transfers
        self._path = path
        self._closed = False

    @property
    def name(self) -> str:
        return self._temp_name

    def __getattr__(self, name: str):
        return getattr(self._temp_file, name)

    def __enter__(self) -> '_PhoneUploadStream':
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close(commit=exc_type is None)
        return False

    def close(self, commit: bool = True) -> None:
        if self._closed:
            return
        self._temp_file.close()
        try:
            if commit:
                self._transfers.upload_and_notify(self._temp_name, self._path)
        finally:
            self._closed = True
            try:
                os.remove(self._temp_name)
            except FileNotFoundError:
                pass
