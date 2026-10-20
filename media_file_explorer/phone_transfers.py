"""fman copy and move task construction for phone endpoints."""
import os
import posixpath
from io import UnsupportedOperation

from fman import Task
import fman.fs
from fman.url import as_human_readable, as_url, basename, splitscheme


class PhoneTransfers:
    def __init__(self, phone_fs):
        self.fs = phone_fs

    def prepare_copy(self, src_url, dst_url):
        src_scheme, src = splitscheme(src_url)
        dst_scheme, dst = splitscheme(dst_url)
        if src_scheme == self.fs.scheme and dst_scheme == 'file://':
            local_target = as_human_readable(dst_url)
            if self.fs.is_dir(src):
                local_target = os.path.join(local_target, posixpath.basename(src.rstrip('/')))
            return self._download_tree(src, local_target)
        if src_scheme == 'file://' and dst_scheme == self.fs.scheme:
            local_source = as_human_readable(src_url)
            if os.path.isdir(local_source):
                target = dst.rstrip('/') + '/' + os.path.basename(local_source.rstrip('\\/'))
                return self._upload_tree(local_source, target)
            return self._upload_file(local_source, dst)
        raise UnsupportedOperation('Phone copies support only phone↔PC transfers')

    def _download_tree(self, remote, local):
        tasks = []
        if self.fs.is_dir(remote):
            tasks.append(_DirectoryTask('Creating ' + os.path.basename(local), lambda: os.makedirs(local, exist_ok=True)))
            for name in self.fs.iterdir(remote):
                child = remote.rstrip('/') + '/' + name
                tasks.extend(self._download_tree(child, os.path.join(local, name)))
        else:
            entry = self.fs._entry(remote)
            api_path = self.fs._api_path(remote)
            client = self.fs._client(self.fs._parts(remote)[0])
            parent = os.path.dirname(local)
            tasks.append(_DirectoryTask('Creating ' + os.path.basename(parent), lambda: os.makedirs(parent, exist_ok=True)))
            tasks.append(_DownloadTask(client, api_path, local, entry.get('size') or 0))
        return tasks

    def _upload_tree(self, local, remote):
        tasks = []
        if os.path.isdir(local):
            tasks.append(_DirectoryTask('Creating ' + os.path.basename(remote), self._mkdir_if_missing, (remote,)))
            for name in os.listdir(local):
                tasks.extend(self._upload_tree(os.path.join(local, name), remote.rstrip('/') + '/' + name))
        else:
            tasks.append(_UploadTask(self, local, remote, os.path.getsize(local)))
        return tasks

    def _upload_file(self, local, remote):
        parent = posixpath.dirname(remote)
        tasks = [_DirectoryTask('Creating ' + posixpath.basename(parent), self._mkdir_if_missing, (parent,))]
        tasks.append(_UploadTask(self, local, remote, os.path.getsize(local)))
        return tasks

    def _mkdir_if_missing(self, path):
        if not self.fs.exists(path):
            self.fs.mkdir(path)

    def _upload_and_notify(self, local, remote):
        parts = self.fs._parts(remote)
        existed = self.fs.exists(remote)
        self.fs._client(parts[0]).upload(local, self.fs._api_path(remote))
        self.fs._invalidate(remote)
        if existed:
            self.fs.notify_file_changed(remote)
        else:
            self.fs.notify_file_added(remote)

    def prepare_move(self, src_url, dst_url):
        src_scheme, src = splitscheme(src_url)
        dst_scheme, dst = splitscheme(dst_url)
        if src_scheme == self.fs.scheme and dst_scheme == self.fs.scheme:
            src_parts, dst_parts = self.fs._parts(src), self.fs._parts(dst)
            if len(src_parts) >= 3 and len(dst_parts) >= 3 and src_parts[:2] == dst_parts[:2]:
                task = Task('Renaming ' + basename(src_url), size=1, fn=self.fs.rename, args=(src, dst))
                return [task]
            raise UnsupportedOperation('Phone-to-phone moves are not supported')
        tasks = list(self.prepare_copy(src_url, dst_url))
        if src_scheme == self.fs.scheme:
            cleanup = Task('Cleaning up ' + basename(src_url), size=1, fn=self.fs.delete, args=(src,))
        elif dst_scheme == self.fs.scheme:
            cleanup = Task('Cleaning up ' + basename(src_url), size=1, fn=fman.fs.delete, args=(src_url,))
        else:
            raise UnsupportedOperation()
        cleanup.waits_for_earlier_tasks = True
        tasks.append(cleanup)
        return tasks


class _DirectoryTask(Task):
    blocks_later_tasks = True
    def __init__(self, title, fn, args=()):
        super().__init__(title, size=1, fn=fn, args=args)

class _DownloadTask(Task):
    def __init__(self, client, api_path, local_path, size):
        super().__init__('Copying ' + os.path.basename(local_path), size=size)
        self.client, self.api_path, self.local_path = client, api_path, local_path
    def __call__(self):
        self.client.download(self.api_path, self.local_path, self._update)
        fman.fs.notify_file_added(as_url(self.local_path))
    def _update(self, current, total):
        if total > 0: self.set_progress(int(current * 100 / total))

class _UploadTask(Task):
    def __init__(self, transfers, local_path, remote_path, size):
        super().__init__('Copying ' + os.path.basename(local_path), size=size)
        self.transfers, self.local_path, self.remote_path = transfers, local_path, remote_path
    def __call__(self):
        parts = self.transfers.fs._parts(self.remote_path)
        existed = self.transfers.fs.exists(self.remote_path)
        client = self.transfers.fs._client(parts[0])
        client.upload(self.local_path, self.transfers.fs._api_path(self.remote_path), self._update)
        self.transfers.fs._invalidate(self.remote_path)
        if existed:
            self.transfers.fs.notify_file_changed(self.remote_path)
        else:
            self.transfers.fs.notify_file_added(self.remote_path)
    def _update(self, current, total):
        if total > 0: self.set_progress(int(current * 100 / total))
