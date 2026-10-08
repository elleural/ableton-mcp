"""Shared helpers for the audio-level tests of the measurement ear (not a test module)."""
import contextlib
import copy

import pytest

from ears import compare


@contextlib.contextmanager
def memoise_side_metrics():
    """Measure each (take, variation) once while the context is open.

    compare.side_metrics measures every tier and every part, about two seconds a take, and several tests ask for the same
    takes. Yields the real function for the tests that must measure for themselves.
    """
    real = compare.side_metrics
    cache = {}

    def once(take, spec, variation=None):
        key = (str(take.path), variation or (take.variations[0] if take.variations else None))
        if key not in cache:
            cache[key] = real(take, spec, variation)
        return copy.deepcopy(cache[key])

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(compare, "side_metrics", once)
        yield real
