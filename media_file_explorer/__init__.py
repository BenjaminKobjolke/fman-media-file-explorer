"""fman plugin entry point."""
from fman import DirectoryPaneCommand
from .phone_fs import PhoneFileSystem

class ShowPhones(DirectoryPaneCommand):
    aliases = ('Show phones',)
    def __call__(self):
        self.pane.set_path('phone://')
