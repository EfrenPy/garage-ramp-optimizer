"""Tests for the localization layer."""

import pytest

import ramp_optimizer as ro


def test_default_language_is_english():
    # When the test suite runs there is no _lang_es.flag, no
    # RAMP_LANG=es and the binary is not frozen, so the default must
    # be English.
    assert ro.LANGUAGE == "en"


def test_t_passes_through_when_english():
    ro.LANGUAGE = "en"
    assert ro.t("Garage Ramp Optimizer") == "Garage Ramp Optimizer"


def test_t_returns_spanish_when_language_is_es():
    ro.LANGUAGE = "es"
    try:
        assert ro.t("Garage Ramp Optimizer") == "Optimizador de Rampa de Garaje"
        assert ro.t("Ramp data") == "Datos de la rampa"
        assert ro.t("Calculate and generate blueprints") == \
            "Calcular y generar planos"
    finally:
        ro.LANGUAGE = "en"


def test_t_falls_back_to_input_for_unknown_keys():
    ro.LANGUAGE = "es"
    try:
        assert ro.t("a string that is not in the translation dictionary") == \
            "a string that is not in the translation dictionary"
    finally:
        ro.LANGUAGE = "en"


def test_translation_dict_has_no_empty_values():
    """Spot-check that we did not commit empty string mappings."""
    d = ro._TRANSLATIONS_ES
    empty = [k for k, v in d.items() if not v]
    assert not empty, f"empty translations for: {empty}"
