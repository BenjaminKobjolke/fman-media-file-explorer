"""Minimal fman URL helpers used by plugin tests."""

import os


def normalize(url):
    return url


def splitscheme(url):
    scheme, separator, path = url.partition('://')
    return (scheme + '://' if separator else ''), path


def as_human_readable(url):
    scheme, path = splitscheme(url)
    if scheme == 'file://':
        if len(path) > 2 and path[0] == '/' and path[2] == ':':
            path = path[1:]
        return path
    return url


def as_url(path):
    return 'file://' + os.path.abspath(path)


def basename(url):
    return os.path.basename(splitscheme(url)[1].rstrip('/'))
