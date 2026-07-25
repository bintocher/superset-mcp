"""Shared pytest fixtures for mcp-superset tests."""

import os

# mcp_superset.server builds its auth strategy at import time, so tests that
# import it need a configuration present before that import happens.
os.environ.setdefault("SUPERSET_BASE_URL", "https://superset.example.com")
os.environ.setdefault("SUPERSET_SESSION_COOKIE", "test-cookie")
