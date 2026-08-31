"""Komendy glosowe per jezyk: kazdy jezyk trafia w swoje slowa i nie widzi cudzych.

Czyste testy logiki dopasowania, bez audio i bez sieci. Warstwe wymowy
sprawdzaja testy e2e na fixture'ach TTS (tests/e2e/test_multilang.py).
"""

from __future__ import annotations

import pytest

from app.config import Settings
from controls import command_languages as cl
from controls.mapping_manager import MappingManager

LOCALE_BY_PREFIX = {
    "pl": "pl_PL", "en": "en_US", "de": "de_DE", "fr": "fr_FR", "es": "es_ES",
    "it": "it_IT", "pt": "pt_BR", "ru": "ru_RU", "tr": "tr_TR", "ko": "ko_KR",
    "ja": "ja_JP", "zh": "zh_CN", "th": "th_TH", "vi": "vi_VN", "id": "id_ID",
    "ar": "ar_AE", "cs": "cs_CZ", "el": "el_GR", "hu": "hu_HU", "ro": "ro_RO",
}


def manager(locale: str, merge: bool = False, mode: str = "letters") -> MappingManager:
    m = MappingManager(Settings(language=locale, merge_command_languages=merge))
    m.mode = mode
    return m


def expected_key(slot: str, settings: Settings) -> str:
    if slot == cl.FLASH:
        return settings.flash_key
    if slot == cl.SUMM2:
        return settings.summoner2_key
    return slot


@pytest.mark.parametrize("prefix", sorted(cl.EXTRAS_BY_LANG))
def test_every_language_matches_its_own_commands(prefix):
    locale = LOCALE_BY_PREFIX[prefix]
    m = manager(locale)
    for phrase, slot in cl.EXTRAS_BY_LANG[prefix].items():
        assert m.match_command(phrase) == expected_key(slot, m.settings), (
            f"{locale}: {phrase!r} nie trafia w {slot}"
        )


@pytest.mark.parametrize("prefix", sorted(cl.LETTERS_BY_LANG))
def test_letter_variants_match(prefix):
    locale = LOCALE_BY_PREFIX[prefix]
    m = manager(locale)
    for phrase, key in cl.LETTERS_BY_LANG[prefix].items():
        assert m.match_command(phrase) == key, f"{locale}: {phrase!r} nie trafia w {key}"


@pytest.mark.parametrize("prefix", sorted(cl.EXTRAS_BY_LANG))
def test_plain_letters_work_everywhere(prefix):
    m = manager(LOCALE_BY_PREFIX[prefix])
    for letter in ("q", "w", "e", "r"):
        assert m.match_command(letter) == letter


def test_polish_words_stay_out_of_other_languages():
    ko = manager("ko_KR")
    assert ko.match_command("błysk") is None
    assert ko.match_command("leczenie") is None
    assert ko.match_command("sklep") is None


def test_korean_words_stay_out_of_polish():
    pl = manager("pl_PL")
    assert pl.match_command("점멸") is None
    assert pl.match_command("귀환") is None


def test_merge_option_brings_every_language_back():
    m = manager("ko_KR", merge=True)
    assert m.match_command("błysk") == m.settings.flash_key
    assert m.match_command("점멸") == m.settings.flash_key
    assert m.match_command("blitz") == m.settings.flash_key


def test_universal_flash_works_in_every_language():
    for prefix in sorted(cl.EXTRAS_BY_LANG):
        m = manager(LOCALE_BY_PREFIX[prefix])
        assert m.match_command("flash") == m.settings.flash_key, prefix


def test_language_without_dictionary_falls_back_to_english():
    m = manager("nl_NL")
    assert m.match_command("ghost") == m.settings.summoner2_key


def test_language_switch_rebuilds_dictionaries():
    m = manager("pl_PL")
    assert m.match_command("błysk") == m.settings.flash_key
    m.settings = Settings(language="ko_KR")
    m.mode = "letters"
    assert m.match_command("błysk") is None
    assert m.match_command("점멸") == m.settings.flash_key


def test_every_ui_language_has_a_dictionary():
    """Kazdy jezyk z panelu ma swoj slownik komend i wariantow liter."""
    for prefix in LOCALE_BY_PREFIX:
        assert prefix in cl.EXTRAS_BY_LANG, f"brak EXTRAS dla {prefix}"
        assert prefix in cl.LETTERS_BY_LANG, f"brak LETTERS dla {prefix}"
