# Ensure the repository root is on PYTHONPATH for test imports
import sys
import pathlib

repo_root = pathlib.Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

# Configure anyio to use asyncio backend (trio is not installed)
import pytest

@pytest.fixture
def anyio_backend():
    return "asyncio"
