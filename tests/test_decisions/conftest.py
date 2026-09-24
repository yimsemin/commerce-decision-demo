from __future__ import annotations

import pytest

from commerce_lab.lenses.registry import BUILTIN_LENS_NAMES, compute_sections, load_lenses


@pytest.fixture(scope="session")
def lenses():
    return load_lenses(BUILTIN_LENS_NAMES)


@pytest.fixture(scope="session")
def computed(lenses, datasets, window):
    """(sections, default params) for the built-in lenses at the latest as-of."""
    return compute_sections(lenses, datasets, window)


@pytest.fixture(scope="session")
def sections(computed):
    return computed[0]


@pytest.fixture(scope="session")
def default_params(computed):
    return computed[1]
