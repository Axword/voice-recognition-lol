"""Lancuchy komend: jedna wypowiedz, kilka klawiszy po kolei.

"kju wu e" ma wcisnac Q, W, E w tej kolejnosci. Trudniejsza polowa zadania to
nie wcisnac niczego, gdy uzytkownik po prostu mowi.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from controls.mapping_manager import MappingManager


def manager(mode: str = "letters", language: str = "pl_PL") -> MappingManager:
    m = MappingManager(Settings(recognition_mode=mode, language=language, combo_enabled=True))
    m.mode = mode
    return m


# --- lancuchy, ktore maja dzialac -------------------------------------


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("kju wu e", ["q", "w", "e"]),
        ("q w e", ["q", "w", "e"]),
        ("kju wu e ar", ["q", "w", "e", "r"]),
        ("e wu", ["e", "w"]),
        ("wu wu", ["w", "w"]),
    ],
)
def test_letter_chains(spoken, expected):
    assert manager().match_sequence(spoken) == expected


@pytest.mark.parametrize("spoken", ["kju i wu i e", "kju oraz wu oraz e", "kju potem wu potem e"])
def test_connectors_are_skipped(spoken):
    assert manager().match_sequence(spoken) == ["q", "w", "e"]


def test_chain_can_mix_letters_and_summoner_spells():
    settings = Settings(recognition_mode="letters", combo_enabled=True)
    assert manager().match_sequence("flash kju") == [settings.flash_key, "q"]


def test_order_is_preserved():
    assert manager().match_sequence("ar e wu kju") == ["r", "e", "w", "q"]


# --- czego lancuch nie moze zrobic ------------------------------------


def test_single_command_is_not_a_chain():
    """Pojedyncza komenda zostaje dla match_command."""
    assert manager().match_sequence("wu") == []


@pytest.mark.parametrize("spoken", ["bo jest", "dzien dobry", "no i wylaczam streama"])
def test_multi_word_commands_stay_whole(spoken):
    """Komenda z kilku slow nie moze zostac rozbita na litery."""
    assert manager().match_sequence(spoken) == []
    assert manager().match_command(spoken) is not None


@pytest.mark.parametrize("spoken", ["kju blablabla", "zupelnie inne zdanie", "kju wu przypadkowo"])
def test_anything_unknown_drops_the_whole_chain(spoken):
    assert manager().match_sequence(spoken) == []


@pytest.mark.parametrize("spoken", ["ale wiesz", "wiesz co", "ty wiesz ale"])
def test_ordinary_speech_does_not_fire_a_chain(spoken):
    """Rozmyte warianty liter sa zwyklymi polskimi slowami, wiec nie skladaja lancucha."""
    assert manager().match_sequence(spoken) == []


def test_chain_length_is_capped():
    limit = MappingManager.COMBO_MAX_KEYS
    too_long = " ".join(["kju"] * (limit + 1))
    assert manager().match_sequence(too_long) == []
    at_limit = " ".join(["kju"] * limit)
    assert manager().match_sequence(at_limit) == ["q"] * limit


def test_empty_text():
    assert manager().match_sequence("") == []
    assert manager().match_sequence("   ") == []


# --- tryb nazw umiejetnosci -------------------------------------------


def test_spell_names_chain_without_being_split():
    m = manager(mode="spells")
    m.load_champion_mappings({"zwodnicza kula": "q", "urok": "e", "duch lisicy": "w"})
    assert m.match_sequence("zwodnicza kula urok") == ["q", "e"]
    assert m.match_sequence("duch lisicy zwodnicza kula") == ["w", "q"]
    assert m.match_sequence("zwodnicza kula") == []


# --- jezyki ------------------------------------------------------------


def test_chain_in_english():
    m = manager(language="en_US")
    assert m.match_sequence("cue double u ee") == ["q", "w", "e"]
    assert m.match_sequence("q and w and e") == ["q", "w", "e"]


def test_chain_in_korean():
    m = manager(language="ko_KR")
    assert m.match_sequence("큐 더블유 이") == ["q", "w", "e"]


# --- akcje specjalne w lancuchu ---------------------------------------


def test_special_actions_inside_a_chain_become_real_keys():
    """"escape" i "random" nie sa klawiszami, wiec musza zostac zamienione."""
    from controller.service import RANDOM_ABILITIES, VoiceService

    service = VoiceService.__new__(VoiceService)
    assert service._resolve_key("escape") == "esc"
    assert service._resolve_key("random") in RANDOM_ABILITIES
    assert service._resolve_key("q") == "q"


def test_chain_with_a_special_action_presses_translated_keys():
    from controller.service import VoiceService

    pressed: list[str] = []

    service = VoiceService.__new__(VoiceService)
    # key_controller jest wlasciwoscia tylko do odczytu, wiec podmieniamy pole,
    # z ktorego czyta.
    service._key_controller = type("Keys", (), {"press_key": lambda _self, key: pressed.append(key)})()
    service._execute(["q", "escape", "w"], "kju anuluj wu")

    assert pressed == ["q", "esc", "w"]


# --- sklejone slowa ----------------------------------------------------

# Whisper skleja szybko wypowiedziane litery w jedno slowo. To sa prawdziwe
# transkrypcje z sesji uzytkownika, nie wymyslone przypadki.


@pytest.mark.parametrize(
    ("heard", "expected"),
    [
        ("qwa", ["q", "w", "e"]),
        ("qwe", ["q", "w", "e"]),
        ("kiuvue", ["q", "w", "e"]),
        ("kuwu e", ["q", "w", "e"]),
        ("kuwe", ["q", "w", "e"]),
        ("q wa", ["q", "w", "e"]),
        ("wa", ["w", "e"]),
    ],
)
def test_merged_letters_are_split(heard, expected):
    assert manager().match_sequence(heard) == expected


@pytest.mark.parametrize(
    ("heard", "expected"),
    [
        ("ku i wu i e", ["q", "w", "e"]),
        ("ku i wu i e i r", ["q", "w", "e", "r"]),
        ("kol i wol i we", ["q", "w", "e"]),
        ("kiu i wloje", ["q", "w", "e"]),
    ],
)
def test_letters_written_as_polish_words(heard, expected):
    """Whisper zapisuje wypowiedziane litery jako slowa: kół, wół, wę."""
    assert manager().match_sequence(heard) == expected


@pytest.mark.parametrize("heard", ["muzyka", "kowly", "wlosy", "kupu a", "zupelnie inne zdanie"])
def test_ordinary_words_are_not_split_into_letters(heard):
    assert manager().match_sequence(heard) == []


def test_long_words_are_never_split():
    """Dluga zbitka to zdanie, nie sklejone litery."""
    long_word = "a" * (MappingManager.COMBO_MAX_TOKEN_CHARS + 1)
    assert manager().match_sequence(long_word) == []


def test_split_prefers_the_most_letters():
    """"kuwe" to ku, w, e, a nie ku plus we."""
    assert manager().match_sequence("kuwe") == ["q", "w", "e"]


def test_spell_mode_does_not_split_words():
    """W trybie nazw umiejetnosci rozbijanie slow tylko szkodzi."""
    m = manager(mode="spells")
    m.load_champion_mappings({"zwodnicza kula": "q", "urok": "e"})
    assert m.match_sequence("qwa") == []
