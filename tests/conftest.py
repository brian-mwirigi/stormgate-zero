"""Keep pytest on the local physics path even when a developer .env has a key."""

import os

os.environ["STORMGATE_OFFLINE"] = "1"
