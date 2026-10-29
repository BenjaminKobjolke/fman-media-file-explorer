"""fman plugin entry point."""
from fman import DirectoryPaneCommand
from .phone_fs import PhoneFileSystem


__all__ = ['PhoneFileSystem', 'ShowPhones']


class ShowPhones(DirectoryPaneCommand):
    aliases = ('Show phones',)
    def __call__(self) -> None:
        self.pane.set_path('phone://')
