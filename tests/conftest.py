"""
xv7 Tests — Root conftest

Shared fixtures and pytest configuration for unit and integration tests.
"""

import pytest


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
