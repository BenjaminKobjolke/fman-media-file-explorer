"""fman filesystem adapter for paired phones."""
from datetime import datetime
from io import UnsupportedOperation
import posixpath
from typing import Any, Iterable, Mapping

from fman.fs import FileSystem, cached
from fman import Task
from fman.url import normalize

from .companion_http import PinnedHttpsClient
from .companion_link import CompanionLink, Phone


class PhoneFileSystem(FileSystem):
    scheme = 'phone://'

    def __init__(self, link: CompanionLink | None = None) -> None:
        super().__init__()
        self.link = link or CompanionLink()
        self._clients = {}
        self._phones = {}

    @staticmethod
    def _clean(path: str) -> str:
        return posixpath.normpath('/' + path).lstrip('/') if path else ''

    def _parts(self, path: str) -> list[str]:
        clean = self._clean(path)
        return clean.split('/') if clean else []

    def _phone(self, name: str) -> Phone:
        for phone in self.link.peers():
            if phone.name == name:
                return phone
        raise FileNotFoundError('Unknown phone: ' + name)

    def _client(self, name: str) -> PinnedHttpsClient:
        phone = self._phone(name)
        if self._phones.get(name) != phone:
            self._phones[name] = phone
            self._clients[name] = PinnedHttpsClient(
                phone.host, phone.port, phone.fingerprint, phone.token
            )
        return self._clients[name]

    def _api_path(self, path: str) -> str:
        parts = self._parts(path)
        if len(parts) < 2:
            raise UnsupportedOperation('A phone share is required')
        return '/' + '/'.join(parts[1:])

    def _remote_listing(self, folder_path: str) -> list[dict[str, Any]]:
        parts = self._parts(folder_path)
        if not parts:
            raise ValueError('Root is not a remote listing')
        api_path = '/' if len(parts) == 1 else '/' + '/'.join(parts[1:])
        result = self._client(parts[0]).get_json('/v1/list', {'path': api_path})
        return result.get('entries', [])

    @cached
    def _listing(self, folder_path: str) -> list[Mapping[str, Any]]:
        parts = self._parts(folder_path)
        if not parts:
            return [
                {'name': p.name, 'isDirectory': True}
                for p in self.link.peers()
            ]
        if len(parts) == 1:
            return self._remote_listing(folder_path)
        return self._remote_listing(folder_path)

    def get_default_columns(self, path: str) -> tuple[str, str, str]:
        return 'core.Name', 'core.Size', 'core.Modified'

    def iterdir(self, path: str) -> list[str]:
        return [entry['name'] for entry in self._listing(path)]

    def _entry(self, path: str) -> Mapping[str, Any]:
        parts = self._parts(path)
        if len(parts) < 2:
            raise FileNotFoundError(path)
        name = parts[-1]
        for entry in self._listing(posixpath.dirname('/'.join(parts))):
            if entry['name'] == name:
                return entry
        raise FileNotFoundError(path)

    def is_dir(self, existing_path: str) -> bool:
        parts = self._parts(existing_path)
        if not parts:
            return True
        if len(parts) == 1:
            self._phone(parts[0])
            return True
        return bool(self._entry(existing_path)['isDirectory'])

    def exists(self, path: str) -> bool:
        parts = self._parts(path)
        if not parts:
            return True
        if len(parts) == 1:
            try:
                self._phone(parts[0])
                return True
            except FileNotFoundError:
                return False
        try:
            self._entry(path)
            return True
        except FileNotFoundError:
            return False

    def resolve(self, path: str) -> str:
        clean = self._clean(path)
        if clean and not self.exists(clean):
            raise FileNotFoundError(self.scheme + clean)
        return normalize(self.scheme + clean)

    def size_bytes(self, path: str) -> int | None:
        entry = self._entry(path)
        return None if entry.get('isDirectory') else entry.get('size')

    def modified_datetime(self, path: str) -> datetime | None:
        entry = self._entry(path)
        millis = entry.get('modified')
        return (
            datetime.fromtimestamp(millis / 1000)
            if millis is not None
            else None
        )

    def _invalidate(self, path: str, related: Iterable[str] = ()) -> None:
        for candidate in {path, posixpath.dirname(path), *related}:
            self.cache.clear(candidate)

    def mkdir(self, path: str) -> None:
        parts = self._parts(path)
        if len(parts) < 3:
            raise UnsupportedOperation('Phone and share roots cannot be created')
        self._client(parts[0]).post_json('/v1/mkdir', {'path': self._api_path(path)})
        self._invalidate(path)
        self.notify_file_added(path)

    def delete(self, path: str) -> None:
        parts = self._parts(path)
        if len(parts) < 3:
            raise UnsupportedOperation('Phone and share roots cannot be deleted')
        self._client(parts[0]).delete('/v1/entry', {'path': self._api_path(path)})
        self._invalidate(path)
        self.notify_file_removed(path)

    def prepare_delete(self, path: str) -> Task:
        return Task(
            'Deleting ' + posixpath.basename(path.rstrip('/')),
            size=1,
            fn=self.delete,
            args=(path,),
        )

    def move_to_trash(self, path: str) -> None:
        raise UnsupportedOperation('Phones do not support trash; use permanent delete')

    def prepare_trash(self, path: str) -> None:
        raise UnsupportedOperation('Phones do not support trash; use permanent delete')

    def rename(self, source: str, destination: str) -> None:
        source_parts, target_parts = self._parts(source), self._parts(destination)
        if (
            len(source_parts) < 3
            or len(target_parts) < 3
            or source_parts[0] != target_parts[0]
            or source_parts[1] != target_parts[1]
        ):
            raise UnsupportedOperation('Rename must stay within the same phone share')
        client = self._client(source_parts[0])
        client.post_json(
            '/v1/rename',
            {
                'from': self._api_path(source),
                'to': self._api_path(destination),
            },
        )
        self._invalidate(source, (destination,))
        self.notify_file_removed(source)
        self.notify_file_added(destination)

    def prepare_copy(self, src_url: str, dst_url: str) -> list[Task]:
        from .phone_transfers import PhoneTransfers
        return PhoneTransfers(self).prepare_copy(src_url, dst_url)

    def prepare_move(self, src_url: str, dst_url: str) -> list[Task]:
        from .phone_transfers import PhoneTransfers
        return PhoneTransfers(self).prepare_move(src_url, dst_url)

    def copy(self, src_url: str, dst_url: str) -> None:
        for task in self.prepare_copy(src_url, dst_url):
            task()

    def move(self, src_url: str, dst_url: str) -> None:
        for task in self.prepare_move(src_url, dst_url):
            task()
