"""The Power-Play species preset (program Task 5, dark): the flag's inert
contract, the two-key window dict (the import-time-copy rule), the ONE
window-override mechanism, and the one-batch manifest registration."""
import pytest

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS, collect_manifest
from engine_alpha.structure.htf import timeframe_windows, window_override


def test_flag_is_dark_and_the_dict_moves_exactly_two_names():
    assert settings.POWER_PLAY_PRESET_ENABLED is False
    # The clock and its import-time copy move TOGETHER, and nothing else —
    # program Task 1's audit verdict. A third key here is a design change.
    assert set(settings.POWER_PLAY_WINDOWS) == {
        "MIN_BASE_DAYS", "PIP_MACRO_MIN_BASE_BARS"}
    assert (settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"]
            == settings.POWER_PLAY_WINDOWS["PIP_MACRO_MIN_BASE_BARS"])
    # The species clock is a SHORTER read than the default, never a loosening
    # of anything else.
    assert 0 < settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"] < settings.MIN_BASE_DAYS


def test_window_override_scopes_and_restores_both_names():
    before = (settings.MIN_BASE_DAYS, settings.PIP_MACRO_MIN_BASE_BARS)
    with window_override(settings.POWER_PLAY_WINDOWS):
        clock = settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"]
        assert settings.MIN_BASE_DAYS == clock
        assert settings.PIP_MACRO_MIN_BASE_BARS == clock   # the copy FOLLOWS
    assert (settings.MIN_BASE_DAYS, settings.PIP_MACRO_MIN_BASE_BARS) == before


def test_window_override_restores_on_exception():
    before = settings.MIN_BASE_DAYS
    with pytest.raises(RuntimeError):
        with window_override({"MIN_BASE_DAYS": 7}):
            assert settings.MIN_BASE_DAYS == 7
            raise RuntimeError("mid-read crash")
    assert settings.MIN_BASE_DAYS == before


def test_window_override_refuses_a_typo_before_setting_anything():
    before = settings.MIN_BASE_DAYS
    with pytest.raises(AttributeError):
        with window_override({"MIN_BASE_DAYS_TYPO": 7}):
            pass                                           # pragma: no cover
    assert settings.MIN_BASE_DAYS == before


def test_timeframe_windows_still_delegates_byte_identically():
    before = settings.MIN_BASE_DAYS
    with timeframe_windows("weekly"):
        assert settings.MIN_BASE_DAYS == settings.HTF_WEEKLY_WINDOWS["MIN_BASE_DAYS"]
    assert settings.MIN_BASE_DAYS == before


def test_manifest_carries_the_species_batch():
    batch = {"POWER_PLAY_PRESET_ENABLED", "POWER_PLAY_STORY_FORM_ENABLED",
             "POWER_PLAY_WINDOWS",
             "POWER_PLAY_POLE_MIN_GAIN", "POWER_PLAY_POLE_WINDOW_BARS"}
    assert batch <= set(ENGINE_SETTINGS_KEYS)
    manifest = collect_manifest()
    assert manifest["POWER_PLAY_PRESET_ENABLED"] is False
    assert manifest["POWER_PLAY_WINDOWS"]["MIN_BASE_DAYS"] == \
        settings.POWER_PLAY_WINDOWS["MIN_BASE_DAYS"]
