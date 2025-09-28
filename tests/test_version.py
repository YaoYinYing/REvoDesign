from packaging import version
from REvoDesign import __version__


class TestVersionNumber:
    def test_current_version(self):
        version.parse(__version__)