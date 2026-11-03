"""Keep pytest on the local physics path even when a developer .env has a key."""

import os

os.environ["STORMGATE_OFFLINE"] = "1"

import pytest


@pytest.fixture(autouse=True)
def _restore_design_storm():
    from backend.physics.storm_catalog import select

    select("ds-1482")
    yield
    select("ds-1482")
