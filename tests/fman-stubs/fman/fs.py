"""Minimal fman filesystem API surface used by plugin tests."""

from functools import wraps


class _Cache:
    def clear(self, _path=None):
        pass


class FileSystem:
    def __init__(self):
        self.cache = _Cache()

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
