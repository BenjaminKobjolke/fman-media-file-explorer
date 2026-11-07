"""Minimal fman filesystem API surface used by plugin tests."""

from functools import wraps


class _Cache:
    def __init__(self, filesystem):
        self._filesystem = filesystem

    def clear(self, path=None):
        for name, values in vars(self._filesystem).items():
            if not name.startswith('_test_cached_') or not isinstance(values, dict):
                continue
            if path is None:
                values.clear()
            else:
                values.pop((path,), None)


class FileSystem:
    def __init__(self):
        self.cache = _Cache(self)

    def notify_file_added(self, _path):
        pass

    def notify_file_removed(self, _path):
        pass

    def notify_file_changed(self, _path):
        pass


def cached(function):
    cache_name = '_test_cached_' + function.__name__

    @wraps(function)
    def wrapper(instance, *args):
        values = getattr(instance, cache_name, None)
        if values is None:
            values = {}
            setattr(instance, cache_name, values)
        if args not in values:
            values[args] = function(instance, *args)
        return values[args]

    return wrapper


def delete(_path):
    pass


def notify_file_added(_path):
    pass
