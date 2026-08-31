"""Paths, settings persistence, legacy migration and version comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import config, paths, version

# --- paths ---------------------------------------------------------------


def test_lolvoice_home_isolates_everything(lolvoice_home):
    home = Path(lolvoice_home)
    for directory in (paths.CONFIG_DIR, paths.DATA_DIR, paths.LOG_DIR, paths.CACHE_DIR, paths.MODELS_DIR):
        assert home in directory.parents or directory == home
    assert home / "config" / "config.json" == paths.CONFIG_FILE
    assert home / "data" / "runtime.json" == paths.RUNTIME_FILE


def test_refresh_follows_a_moved_home(tmp_path, monkeypatch):
    other = tmp_path / "other-home"
    monkeypatch.setenv("LOLVOICE_HOME", str(other))
    paths.refresh()
    assert other / "config" / "config.json" == paths.CONFIG_FILE
    paths.ensure_dirs()
    assert paths.LOG_DIR.is_dir()
    assert paths.MODELS_DIR.is_dir()


def test_ensure_dirs_is_idempotent(lolvoice_home):
    paths.ensure_dirs()
    paths.ensure_dirs()
    assert paths.CACHE_DIR.is_dir()


def test_bundled_dir_holds_the_shipped_data(lolvoice_home):
    assert (paths.bundled_dir() / "data" / "engines.json").is_file()
    assert (paths.bundled_dir() / "version.json").is_file()


def test_nothing_is_written_next_to_the_application(lolvoice_home, workdir):
    config.load()
    config.update({"flash_key": "f"})
    assert not (Path(workdir) / "config.json").exists()
    assert not (Path(workdir) / "config").exists()


# --- defaults and persistence ---------------------------------------------


def test_first_load_writes_the_defaults(lolvoice_home):
    assert not paths.CONFIG_FILE.exists()
    loaded = config.load()
    assert loaded.recognition_mode == "spells"
    assert loaded.flash_key == "d"
    assert loaded.summoner2_key == "f"
    assert paths.CONFIG_FILE.is_file()
    assert json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))["recognition_mode"] == "spells"


def test_load_is_cached_until_reset(lolvoice_home):
    first = config.load()
    assert config.load() is first
    config.reset_cache()
    assert config.load() is not first


def test_update_applies_a_partial_patch(lolvoice_home):
    config.load()
    updated = config.update({"spell_sensitivity": "low"})
    assert updated.spell_sensitivity == "low"
    assert updated.language == "pl_PL"
    config.reset_cache()
    assert config.load().spell_sensitivity == "low"


def test_update_can_clear_a_nullable_field(lolvoice_home):
    config.update({"skipped_version": "1.2.3"})
    assert config.load().skipped_version == "1.2.3"
    config.update({"skipped_version": None})
    assert config.load().skipped_version is None


def test_update_ignores_none_for_non_nullable_fields(lolvoice_home):
    config.update({"language": "en_US"})
    config.update({"language": None})
    assert config.load().language == "en_US"


def test_unknown_keys_are_ignored(lolvoice_home):
    paths.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_FILE.write_text(
        json.dumps({"language": "en_US", "who_is_this": 42}), encoding="utf-8"
    )
    config.reset_cache()
    loaded = config.load()
    assert loaded.language == "en_US"
    assert not hasattr(loaded, "who_is_this")


# --- legacy migration ------------------------------------------------------


def _write_legacy(directory: Path, payload: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_legacy_config_directory_is_migrated(lolvoice_home, workdir):
    _write_legacy(
        Path(workdir) / "config",
        {
            "recognition_mode": "letters",
            "spell_sensitivity": "high",
            "language": "pl_PL",
            "flash_key": "D",
            "ui_language": "pl_PL",
        },
    )
    config.reset_cache()
    loaded = config.load()

    assert loaded.recognition_mode == "letters"
    assert loaded.spell_sensitivity == "high"
    assert loaded.flash_key == "d"  # old builds stored it upper case
    assert paths.CONFIG_FILE.is_file()
    on_disk = json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
    assert on_disk["flash_key"] == "d"


def test_legacy_root_config_is_migrated(lolvoice_home, workdir):
    (Path(workdir) / "config.json").write_text(
        json.dumps({"language": "en_US", "recognition_mode": "letters"}), encoding="utf-8"
    )
    config.reset_cache()
    loaded = config.load()
    assert loaded.language == "en_US"
    assert loaded.recognition_mode == "letters"


def test_legacy_config_directory_wins_over_the_root_file(lolvoice_home, workdir):
    _write_legacy(Path(workdir) / "config", {"language": "en_US"})
    (Path(workdir) / "config.json").write_text(json.dumps({"language": "pl_PL"}), encoding="utf-8")
    config.reset_cache()
    assert config.load().language == "en_US"


def test_legacy_fields_that_no_longer_exist_are_dropped(lolvoice_home, workdir):
    _write_legacy(
        Path(workdir) / "config",
        {"recognition_accuracy_threshold": 0.75, "min_score_threshold": 15.0, "language": "pl_PL"},
    )
    config.reset_cache()
    loaded = config.load()
    assert loaded.language == "pl_PL"
    assert "recognition_accuracy_threshold" not in loaded.model_dump()


def test_migration_is_skipped_once_the_real_config_exists(lolvoice_home, workdir):
    config.save(config.Settings(language="en_US"))
    _write_legacy(Path(workdir) / "config", {"language": "pl_PL"})
    config.reset_cache()
    assert config.load().language == "en_US"


def test_corrupt_legacy_file_is_ignored(lolvoice_home, workdir):
    legacy = Path(workdir) / "config"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "config.json").write_text("{{{ broken", encoding="utf-8")
    config.reset_cache()
    assert config.load().language == "pl_PL"


# --- damaged files ----------------------------------------------------------


def test_corrupt_config_falls_back_to_defaults(lolvoice_home):
    paths.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_FILE.write_text("not json at all", encoding="utf-8")
    config.reset_cache()
    loaded = config.load()
    assert loaded.recognition_mode == "spells"
    assert loaded.language == "pl_PL"


def test_empty_config_file_falls_back_to_defaults(lolvoice_home):
    paths.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_FILE.write_text("", encoding="utf-8")
    config.reset_cache()
    assert config.load().flash_key == "d"


def test_saving_over_a_corrupt_file_repairs_it(lolvoice_home):
    paths.CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    paths.CONFIG_FILE.write_text("}{", encoding="utf-8")
    config.reset_cache()
    config.update({"theme": "light"})
    assert json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))["theme"] == "light"


def test_atomic_write_leaves_no_temporary_file(lolvoice_home):
    config.update({"theme": "light"})
    leftovers = list(paths.CONFIG_DIR.glob("*.tmp"))
    assert leftovers == []
    assert list(paths.CONFIG_DIR.glob("*")) == [paths.CONFIG_FILE]


def test_saved_file_is_readable_utf8_json(lolvoice_home):
    config.update({"audio_device": "Mikrofon Zewnętrzny"})
    text = paths.CONFIG_FILE.read_text(encoding="utf-8")
    assert "Mikrofon Zewnętrzny" in text
    assert json.loads(text)["audio_device"] == "Mikrofon Zewnętrzny"


# --- version -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("V1.2.3", (1, 2, 3)),
        ("1.2", (1, 2, 0)),
        ("1", (1, 0, 0)),
        ("1.2.3.4", (1, 2, 3)),
        ("1.2.3-beta.1", (1, 2, 3)),
        ("v2.0.0-rc1", (2, 0, 0)),
        ("1.x.3", (1, 0, 3)),
        ("", (0, 0, 0)),
    ],
)
def test_version_parse(raw, expected):
    assert version.parse(raw) == expected


@pytest.mark.parametrize(
    ("candidate", "current", "expected"),
    [
        ("1.2.4", "1.2.3", True),
        ("v1.2.4", "1.2.3", True),
        ("1.2.4", "v1.2.3", True),
        ("1.3", "1.2.9", True),
        ("2", "1.9.9", True),
        ("1.2.3", "1.2.3", False),
        ("1.2.3", "v1.2.3", False),
        ("1.2.2", "1.2.3", False),
        ("1.2.3-beta", "1.2.3", False),
        ("1.2.4-beta", "1.2.3", True),
        ("1.2.3", "1.2.3-beta", False),
        ("1.2", "1.2.0", False),
    ],
)
def test_version_is_newer(candidate, current, expected):
    assert version.is_newer(candidate, current) is expected


def test_get_version_reads_the_shipped_file(lolvoice_home):
    shipped = json.loads((paths.bundled_dir() / "version.json").read_text(encoding="utf-8"))
    assert version.get_version() == shipped["version"]
