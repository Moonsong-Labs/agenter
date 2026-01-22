"""Conftest for manual tests - these are not run via pytest."""

import pytest


# Skip all tests in this directory when run via pytest
def pytest_collection_modifyitems(items):
    for item in items:
        if "/manual/" in str(item.fspath):
            item.add_marker(pytest.mark.skip(reason="Manual tests - run directly with python"))
