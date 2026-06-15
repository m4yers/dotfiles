"""Unit tests for the pint-driven recipe conversion helper.

``_convert_to_metric`` is deterministic and lives in
``curator.vault.replica``. These tests pin its rounding rules,
custom-unit support, and ``None``-fallback behavior so future
refactors do not silently change vault output.
"""
from __future__ import annotations

import pytest

from curator.vault.replica import _convert_to_metric


class TestVolumeConversion:
    def test_cups_round_to_nearest_10ml(self):
        # 2.25 cup = 540 ml (kitchen 240 ml/cup), rounded to
        # nearest 10 ml (≥100 ml policy)
        assert _convert_to_metric(2.25, "cup") == "540 ml"

    def test_cup_under_100ml_rounds_to_nearest_1ml(self):
        # 0.25 cup = 60 ml (kitchen 240 ml/cup), exactly so under
        # the <100 ml nearest-1-ml rule
        assert _convert_to_metric(0.25, "cup") == "60 ml"

    def test_fluid_ounce_to_ml(self):
        # 1 fl oz = 29.57 ml → 30 ml (nearest 1 ml under 100 ml)
        assert _convert_to_metric(1, "fluid_ounce") == "30 ml"

    def test_pint_to_ml(self):
        # 1 US pint = 480 ml (recipe-world override; pint default
        # would be 473.18 ml without the kitchen-volume table)
        assert _convert_to_metric(1, "pint") == "480 ml"

    def test_already_metric_volume_round_trips(self):
        assert _convert_to_metric(500, "milliliter") == "500 ml"


class TestMassConversion:
    def test_pound_to_g(self):
        # 1 lb = 453.59 g → 454 g (nearest 1 g)
        assert _convert_to_metric(1, "pound") == "454 g"

    def test_ounce_to_g(self):
        # 2 oz = 56.7 g → 57 g (nearest 1 g)
        assert _convert_to_metric(2, "ounce") == "57 g"

    def test_already_metric_mass_round_trips(self):
        assert _convert_to_metric(300, "gram") == "300 g"

    def test_custom_stick_unit(self):
        # 1 stick = 113 g (custom curator define; the canonical
        # recipe value is preserved exactly).
        assert _convert_to_metric(1, "stick") == "113 g"

    def test_two_sticks(self):
        # 2 stick = 226 g (nearest 1 g)
        assert _convert_to_metric(2, "stick") == "226 g"


class TestLengthConversion:
    def test_inch_to_cm(self):
        assert _convert_to_metric(1, "inch") == "2.5 cm"

    def test_half_inch_to_cm(self):
        assert _convert_to_metric(0.5, "inch") == "1.3 cm"


class TestDoNotConvert:
    def test_none_amount_returns_none(self):
        assert _convert_to_metric(None, "cup") is None

    def test_none_unit_returns_none(self):
        assert _convert_to_metric(2, None) is None

    def test_both_none_returns_none(self):
        assert _convert_to_metric(None, None) is None

    @pytest.mark.parametrize("unit", [
        "tsp", "teaspoon", "teaspoons", "tbsp", "tablespoon", "tablespoons"
    ])
    def test_kitchen_spoon_units_return_none(self, unit):
        # Kitchen-spoon units stay verbatim by policy.
        assert _convert_to_metric(1, unit) is None

    def test_unknown_unit_returns_none(self):
        # Unitless counts ("3 eggs") commonly arrive as
        # ``unit="egg"`` — pint does not know "egg", so the helper
        # falls through to None and the vault page renders the
        # verbatim ``quantity``.
        assert _convert_to_metric(3, "egg") is None

    def test_garbage_unit_returns_none(self):
        assert _convert_to_metric(1, "not_a_unit_xyz") is None
