import os

import pytest

os.environ.setdefault("POWERPILOT_AUTOPLAY", "0")

from powerpilot.config import Settings  # noqa: E402
from powerpilot.engine import Engine  # noqa: E402
from powerpilot.models import train_models  # noqa: E402
from powerpilot.sites import build_sites  # noqa: E402


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def models(settings):
    return train_models(build_sites(settings.seed), settings, days=4)


@pytest.fixture
def engine(settings, models) -> Engine:
    return Engine(settings, autonomy="assist", models=models)
