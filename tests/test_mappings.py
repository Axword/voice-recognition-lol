"""Voice mappings against the real Data Dragon data.

Every champion in the pinned fixture is checked in both languages: the full
name of Q, W, E and R has to match back to its own key in spells mode. Partial
word variants do not always survive, because different abilities of the same
champion share words. Those cases are collected into
tests/reports/mapping_collisions.json instead of being papered over.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pytest

from app.config import Settings
from controls.mapping_manager import SOURCE_CHAMPION, SOURCE_EXTRA, SOURCE_LETTER, MappingManager

ABILITY_KEYS = ("Q", "W", "E", "R")
DDRAGON_DIR = Path(__file__).resolve().parent / "fixtures" / "ddragon"
LANGUAGES = ("pl_PL", "en_US")

# Champions whose ability names share a word with another of their own
# abilities, so the single word variant cannot resolve to one key. Measured
# against Data Dragon 16.16.1, kept here so a data refresh that changes the
# picture shows up as a failure and not as a silent regression.
KNOWN_COLLISIONS = {
    "pl_PL": {
        "Aphelios",
        "Hwei",
        "Khazix",
        "Malzahar",
        "MonkeyKing",
        "Orianna",
        "Rammus",
        "Vladimir",
        "Ziggs",
    },
    "en_US": {
        "Aphelios",
        "Azir",
        "Hwei",
        "Jax",
        "Khazix",
        "Malzahar",
        "Nunu",
        "Orianna",
        "Zed",
        "Ziggs",
        "Zilean",
    },
}

MIN_CLEAN_RATIO = 0.90


@lru_cache(maxsize=4)
def _champion_data(language: str) -> dict:
    payload = json.loads((DDRAGON_DIR / f"championFull.{language}.json").read_text(encoding="utf-8"))
    return payload.get("data", payload)


def _champion_ids(language: str) -> list[str]:
    return sorted(_champion_data(language).keys())


def _abilities(language: str, champion: str) -> dict[str, str]:
    spells = (_champion_data(language).get(champion) or {}).get("spells") or []
    return {key: spells[index]["name"] for index, key in enumerate(ABILITY_KEYS) if index < len(spells)}


ALL_CASES = [(language, champion) for language in LANGUAGES for champion in _champion_ids(language)]


def _manager(language: str, champion: str, data_managers, **overrides) -> MappingManager:
    settings = Settings(recognition_mode="spells", language=language, **overrides)
    manager = MappingManager(settings)
    manager.load_champion_mappings(data_managers[language].create_voice_mappings(champion))
    return manager


# --- full round trip over every champion ------------------------------


@pytest.mark.parametrize(("language", "champion"), ALL_CASES, ids=lambda value: value)
def test_every_ability_name_matches_its_own_key(language, champion, data_managers):
    abilities = _abilities(language, champion)
    assert abilities, f"{champion} has no spells in the {language} fixture"

    manager = _manager(language, champion, data_managers)
    assert manager.champion_spell_mappings, f"{champion} produced no voice mappings"

    for key, name in abilities.items():
        assert manager.match_command(name) == key.lower(), f"{language} {champion} {key} '{name}'"


def test_fixture_covers_every_champion_in_both_languages():
    assert len(_champion_ids("pl_PL")) == len(_champion_ids("en_US")) == 173
    assert set(_champion_ids("pl_PL")) == set(_champion_ids("en_US"))


def test_fixture_version_is_pinned():
    version = (DDRAGON_DIR.parent / "VERSION").read_text(encoding="utf-8").strip()
    assert version == "16.16.1"
    for language in LANGUAGES:
        payload = json.loads((DDRAGON_DIR / f"championFull.{language}.json").read_text(encoding="utf-8"))
        assert payload["version"] == version


# --- collision report --------------------------------------------------


def _word_variant_failures(language: str, champion: str, data_managers) -> list[dict]:
    manager = _manager(language, champion, data_managers)
    failures: list[dict] = []
    for key, name in _abilities(language, champion).items():
        normalized = manager.normalize(name)
        words = normalized.split()
        if len(words) < 2:
            continue
        for word in words:
            if len(word) < 4:
                continue
            matched = manager.match_command(word)
            if matched != key.lower():
                failures.append({"key": key, "ability": name, "word": word, "matched": matched})
    return failures


@pytest.mark.slow
def test_word_variant_collisions_are_documented(data_managers, reports_dir):
    report: dict = {"ddragon_version": "16.16.1", "languages": {}}

    for language in LANGUAGES:
        champions = _champion_ids(language)
        collisions: dict[str, list[dict]] = {}
        for champion in champions:
            failures = _word_variant_failures(language, champion, data_managers)
            if failures:
                collisions[champion] = failures
        clean = len(champions) - len(collisions)
        report["languages"][language] = {
            "champions": len(champions),
            "clean": clean,
            "colliding": len(collisions),
            "clean_ratio": round(clean / len(champions), 4),
            "collisions": collisions,
        }

    path = Path(reports_dir) / "mapping_collisions.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    for language in LANGUAGES:
        section = report["languages"][language]
        assert section["clean_ratio"] >= MIN_CLEAN_RATIO, f"{language}: {section['clean_ratio']}"
        assert set(section["collisions"]) == KNOWN_COLLISIONS[language], language


def test_collision_report_entries_point_at_a_real_other_ability(data_managers):
    """A collision means the word belongs to another ability, not to nothing."""
    failures = _word_variant_failures("pl_PL", "Orianna", data_managers)
    assert failures
    keys = {failure["matched"] for failure in failures}
    assert keys <= {"q", "w", "e", "r"}
    assert any(failure["word"] == "rozkaz" for failure in failures)


# --- normalization -----------------------------------------------------


def test_polish_diacritics_are_normalized(settings):
    manager = MappingManager(settings(recognition_mode="spells"))
    assert manager.normalize("Zaklęcie Ognia") == "zaklecie ognia"
    assert manager.normalize("ŻÓŁĆ, ŚĆ!") == "zolc sc"
    assert manager.normalize("  Kula   ") == "kula"


def test_diacritic_input_matches_ability_typed_without_diacritics(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    abilities = _abilities("pl_PL", "Ahri")
    for key, name in abilities.items():
        stripped = manager.normalize(name)
        assert manager.match_command(stripped) == key.lower()
        assert manager.match_command(name.upper()) == key.lower()


def test_partial_word_variants_match(data_managers):
    manager = _manager("pl_PL", "Ahri", data_managers)
    abilities = _abilities("pl_PL", "Ahri")
    q_words = [word for word in manager.normalize(abilities["Q"]).split() if len(word) >= 4]
    assert q_words
    for word in q_words:
        assert manager.match_command(word) == "q"


def test_punctuation_is_ignored(data_managers):
    manager = _manager("en_US", "Ahri", data_managers)
    name = _abilities("en_US", "Ahri")["R"]
    assert manager.match_command(f"{name}!!!") == "r"
    assert manager.match_command(f"...{name}?") == "r"


# --- letters mode ------------------------------------------------------


def test_letters_mode_exact_matches(settings):
    manager = MappingManager(settings(recognition_mode="letters"))
    for text, expected in (("q", "q"), ("w", "w"), ("e", "e"), ("r", "r"), ("ult", "r"), ("kju", "q")):
        assert manager.match_command(text) == expected


def test_letters_mode_fuzzy_matches(settings):
    manager = MappingManager(settings(recognition_mode="letters"))
    assert manager.match_command("ultimate") == "r"
    assert manager.match_command("ultymate") == "r"
    assert manager.match_command("dzien dobry") == "q"


def test_letters_mode_ignores_champion_mappings(data_managers, settings):
    settings_value = settings(recognition_mode="letters", language="pl_PL")
    manager = MappingManager(settings_value)
    manager.load_champion_mappings(data_managers["pl_PL"].create_voice_mappings("Ahri"))
    assert manager.match_command("q") == "q"
    assert manager.match_command("wielokrotny bezsensowny tekst bez dopasowania") is None


def test_unknown_text_matches_nothing(settings):
    manager = MappingManager(settings(recognition_mode="spells"))
    assert manager.match_command("zupelnie przypadkowe zdanie o niczym") is None
    assert manager.match_command("") is None


# --- extra commands ----------------------------------------------------


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("flash", "flash_key"),
        ("blysk", "flash_key"),
        ("błysk", "flash_key"),
        ("heal", "summoner2_key"),
        ("leczenie", "summoner2_key"),
        ("smite", "summoner2_key"),
    ],
)
def test_summoner_commands_follow_the_configured_keys(phrase, expected, settings):
    # merge: parametryzacja miesza slowa polskie i angielskie
    value = settings(recognition_mode="spells", flash_key="f", summoner2_key="d", merge_command_languages=True)
    manager = MappingManager(value)
    assert manager.match_command(phrase) == getattr(value, expected)


def test_every_extra_command_resolves_in_spells_mode(settings):
    manager = MappingManager(settings(recognition_mode="spells"))
    for phrase, key in manager.extra_commands.items():
        assert manager.match_command(phrase) == key, phrase


def test_extra_commands_available_in_letters_mode(settings):
    manager = MappingManager(settings(recognition_mode="letters", merge_command_languages=True))
    assert manager.match_command("flash") == "d"
    assert manager.match_command("baza") == "b"
    assert manager.match_command("shop") == "p"
    assert manager.match_command("sklep") == "p"
    assert manager.match_command("escape") == "escape"
    assert manager.match_command("anuluj") == "escape"
    assert manager.match_command("random") == "random"
    assert manager.match_command("stop") == "s"


# Regression: these nine phrases used to be swallowed by fuzzy letter matching
# in letters mode ("back" pressed E, "heal" pressed Q). match_command now tries
# an exact hit in extra_commands before any fuzzy matching, so they resolve to
# their own command in every mode.
PREVIOUSLY_SHADOWED = ("heal", "hil", "duch", "halt", "back", "powrot", "base", "losowa", "losowo")


@pytest.mark.parametrize("mode", ["letters", "spells"])
@pytest.mark.parametrize("phrase", PREVIOUSLY_SHADOWED)
def test_extra_commands_are_never_shadowed_by_fuzzy_ability_matching(mode, phrase, settings):
    manager = MappingManager(settings(recognition_mode=mode, merge_command_languages=True))
    assert manager.match_command(phrase) == manager.extra_commands[phrase]


@pytest.mark.parametrize("mode", ["letters", "spells"])
def test_no_extra_command_is_shadowed_in_either_mode(mode, settings):
    manager = MappingManager(settings(recognition_mode=mode))
    shadowed = {
        phrase: manager.match_command(phrase)
        for phrase, key in manager.extra_commands.items()
        if manager.match_command(phrase) != key
    }
    assert shadowed == {}


def test_extra_commands_are_not_shadowed_with_champion_mappings_loaded(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers, merge_command_languages=True)
    for phrase in PREVIOUSLY_SHADOWED:
        assert manager.match_command(phrase) == manager.extra_commands[phrase]


def test_letter_commands_still_work_after_the_extra_command_fix(settings):
    """Guard for the other direction: letters must not lose their own matches."""
    manager = MappingManager(settings(recognition_mode="letters"))
    for phrase, key in manager.ability_mappings_exact.items():
        assert manager.match_command(phrase) == key
    for phrase, key in manager.ability_mappings_fuzzy.items():
        assert manager.match_command(phrase) == key
    assert manager.match_command("ultimate") == "r"
    assert manager.match_command("ultymate") == "r"


def test_default_summoner_keys(settings):
    manager = MappingManager(settings(merge_command_languages=True))
    assert manager.match_command("flash") == "d"
    assert manager.match_command("heal") == "f"


def test_extra_commands_survive_champion_mappings(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    assert manager.match_command("flash") == "d"
    assert manager.match_command("escape") == "escape"


# --- modes and cache ---------------------------------------------------


def test_mode_switch_rebuilds_active_mappings(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    spells_count = len(manager.active_mappings)
    assert manager.mode == "spells"

    manager.mode = "letters"
    assert manager.mode == "letters"
    assert manager.match_command("q") == "q"
    assert len(manager.active_mappings) != spells_count

    manager.mode = "spells"
    assert manager.match_command(_abilities("pl_PL", "Ahri")["Q"]) == "q"


def test_unknown_mode_behaves_like_letters(settings):
    """An unknown mode normalizes to letters in the matcher, not only in the dictionaries."""
    manager = MappingManager(settings(merge_command_languages=True))
    manager.mode = "nonsense"

    assert "q" in manager.active_mappings
    for phrase, key in (("q", "q"), ("w", "w"), ("e", "e"), ("r", "r"), ("ult", "r")):
        assert manager.match_command(phrase) == key
    assert manager.match_command("ultimate") == "r"
    assert manager.match_command("flash") == "d"
    assert manager.match_command("back") == "b"


def test_unknown_mode_matches_letters_even_with_champion_mappings(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    manager.mode = "nonsense"
    assert manager.match_command("q") == "q"
    assert manager.match_command("escape") == "escape"


def test_cache_is_dropped_after_loading_a_new_champion(data_managers, settings):
    ahri_q = _abilities("pl_PL", "Ahri")["Q"]
    manager = _manager("pl_PL", "Ahri", data_managers)
    assert manager.match_command(ahri_q) == "q"
    assert manager.command_cache

    manager.load_champion_mappings(data_managers["pl_PL"].create_voice_mappings("Garen"))
    assert manager.command_cache == {}

    garen_w = _abilities("pl_PL", "Garen")["W"]
    assert manager.match_command(garen_w) == "w"
    assert manager.normalize(ahri_q) not in manager.champion_spell_mappings


def test_cache_is_dropped_when_settings_change(settings):
    manager = MappingManager(settings(flash_key="d"))
    assert manager.match_command("flash") == "d"
    assert manager.command_cache

    manager.settings = settings(flash_key="f")
    assert manager.command_cache == {}
    assert manager.match_command("flash") == "f"


def test_cache_is_dropped_on_mode_change(settings):
    manager = MappingManager(settings(recognition_mode="letters"))
    assert manager.match_command("q") == "q"
    assert manager.command_cache
    manager.mode = "spells"
    assert manager.command_cache == {}


def test_reset_to_default_clears_champion_mappings(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    assert manager.match_command(_abilities("pl_PL", "Ahri")["Q"]) == "q"

    manager.reset_to_default()
    assert manager.champion_spell_mappings == {}
    assert manager.command_cache == {}
    assert manager.match_command("flash") == "d"


def test_sensitivity_changes_the_threshold(settings):
    manager = MappingManager(settings(spell_sensitivity="low"))
    assert manager.get_statistics()["spell_threshold"] == pytest.approx(0.75)
    manager.set_sensitivity("high")
    assert manager.get_statistics()["spell_threshold"] == pytest.approx(0.40)
    assert manager.command_cache == {}


# --- panel view --------------------------------------------------------


def test_describe_mappings_shape(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    rows = manager.describe_mappings()
    assert rows
    assert all(set(row) == {"phrase", "key", "source"} for row in rows)
    sources = {row["source"] for row in rows}
    assert sources == {SOURCE_CHAMPION, SOURCE_EXTRA}
    phrases = [row["phrase"] for row in rows]
    assert len(phrases) == len(set(phrases))

    manager.mode = "letters"
    letter_sources = {row["source"] for row in manager.describe_mappings()}
    assert letter_sources == {SOURCE_LETTER, SOURCE_EXTRA}


def test_statistics_report_current_state(data_managers, settings):
    manager = _manager("pl_PL", "Ahri", data_managers)
    stats = manager.get_statistics()
    assert stats["mode"] == "spells"
    assert stats["champion_spells"] > 0
    assert stats["total_active"] == len(manager.active_mappings)
