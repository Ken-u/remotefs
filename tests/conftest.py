"""Pytest configuration for RemoteFS tests."""

import sys
from unittest.mock import MagicMock

# Mock fuse module before any tests import it
# This is necessary because libfuse may not be available in the test environment
class MockFUSE:
    """Mock FUSE class for testing."""
    def __init__(self, *args, **kwargs):
        # Don't call super().__init__() to avoid object.__init__
        pass

sys.modules['fuse'] = MagicMock()
sys.modules['fuse'].FUSE = MockFUSE