"""Minimal fman API surface used to import the plugin in tests."""


class DirectoryPaneCommand:
    pass


class Task:
    def __init__(self, title, size=0, fn=None, args=()):
        self.title = title
        self.size = size
        self.fn = fn
        self.args = args

    def __call__(self):
        if self.fn is not None:
            return self.fn(*self.args)

    def set_progress(self, _progress):
        pass


def load_json(_name, default=None):
    return default


def save_json(_name, _value):
    pass
