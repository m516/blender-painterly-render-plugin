"""Fixtures for the oracle tests (T1.3)."""

import pytest
from painterly_analysis import oracle as oracle_module


@pytest.fixture
def oracle():
    """The ``painterly_analysis.oracle`` module.

    Fails with a clear message when the ``smallpaint_oracle`` binary has not been built.
    """
    binary = oracle_module.oracle_binary()
    if not binary.is_file():
        pytest.fail(
            f"smallpaint_oracle not found at {binary}. Run `make build` first "
            "(or set PAINTERLY_BUILD_DIR to the build directory that contains it).",
            pytrace=False,
        )
    return oracle_module
