"""E2E bez modelu: PCM -> transkrypcja (atrapa) -> dopasowanie -> klawisz.

Ten plik jest celowo pozbawiony markerow slow i audio, wiec chodzi na kazdym PR.
Pilnuje okablowania calego toru komend: VoiceService.feed_pcm bierze surowy PCM,
puszcza go przez podmieniona transkrypcje (set_transcriber), czysci tekst,
dopasowuje do mapowan bohatera z Data Dragon i wciska klawisz.

Prawdziwe MP3 z tests/fixtures/audio sa tu dekodowane naprawde, przez ffmpeg,
wiec tor dekodowania tez jest sprawdzany. Rozpoznawaniem mowy zajmuje sie
test_recognition.py, ktory potrzebuje modelu.
"""

from __future__ import annotations

import audio_support as support
import pytest

# Frazy dobrane recznie: polskie znaki diakrytyczne i nazwy wielowyrazowe.
DIACRITIC_CASES = [
    ("pl_PL", "Ahri", "Widmowa Szarża", "r"),
    ("pl_PL", "Ahri", "Zwodnicza Kula", "q"),
    ("pl_PL", "Yasuo", "Ściana Wichru", "w"),
    ("pl_PL", "Yasuo", "Zamaszyste Cięcie", "e"),
    ("pl_PL", "Katarina", "Skaczące Ostrza", "q"),
    ("pl_PL", "Katarina", "Lotos Śmierci", "r"),
    ("pl_PL", "Thresh", "Wyrok Śmierci", "q"),
    ("pl_PL", "Thresh", "Mroczne Przejście", "w"),
    ("pl_PL", "Hwei", "Spirala Rozpaczy", "r"),
    ("en_US", "Jinx", "Switcheroo!", "q"),
    ("en_US", "Lux", "Final Spark", "r"),
    ("en_US", "Aatrox", "The Darkin Blade", "q"),
]


def _fixtures(language: str) -> list[support.AudioFixture]:
    return support.load_fixtures(language)


ALL_FIXTURES = [fixture for language in support.LANGUAGES for fixture in _fixtures(language)]


@pytest.fixture
def service_pl():
    service, keys = support.make_service("pl_PL")
    return service, keys


# --- tor bez plikow ---------------------------------------------------


@pytest.mark.parametrize(("language", "champion", "phrase", "expected"), DIACRITIC_CASES)
def test_phrase_reaches_the_right_key(language: str, champion: str, phrase: str, expected: str) -> None:
    """Fraza z Data Dragon, wstrzyknieta jako transkrypcja, wciska wlasciwy klawisz."""
    service, keys = support.make_service(language)
    mappings = support.load_champion(service, champion, language)
    assert mappings, f"brak mapowan dla {champion} ({language})"

    service.set_transcriber(lambda pcm: phrase)
    text = service.feed_pcm(support.silence_pcm(0.3))

    assert text, "feed_pcm nie zwrocil tekstu"
    assert keys.pressed == [expected], f"{phrase!r} -> {keys.pressed}, oczekiwano [{expected!r}]"


def test_transcriber_receives_the_raw_pcm(service_pl) -> None:
    """Bufor podany do feed_pcm trafia do transkrypcji bajt w bajt."""
    service, keys = service_pl
    support.load_champion(service, "Ahri", "pl_PL")
    seen: list[bytes] = []

    def stub(pcm: bytes) -> str:
        seen.append(pcm)
        return "Zwodnicza Kula"

    payload = support.silence_pcm(0.25)
    service.set_transcriber(stub)
    service.feed_pcm(payload)

    assert seen == [payload]
    assert keys.pressed == ["q"]


def test_unknown_phrase_presses_nothing(service_pl) -> None:
    """Tekst spoza mapowan nie wciska klawisza, ale leci jako zdarzenie 'heard'."""
    service, keys = service_pl
    support.load_champion(service, "Ahri", "pl_PL")
    events: list[dict] = []
    service.set_event_sink(events.append)

    service.set_transcriber(lambda pcm: "kompletnie niezwiazane zdanie testowe")
    service.feed_pcm(support.silence_pcm(0.2))

    assert keys.pressed == []
    heard = [event for event in events if event["type"] == "heard"]
    assert heard and heard[-1]["matched"] is None


def test_empty_transcript_is_harmless(service_pl) -> None:
    service, keys = service_pl
    support.load_champion(service, "Ahri", "pl_PL")
    service.set_transcriber(lambda pcm: "")
    assert service.feed_pcm(support.silence_pcm(0.2)) == ""
    assert keys.pressed == []


def test_failing_transcriber_does_not_raise(service_pl) -> None:
    """Wyjatek w transkrypcji ma zostac zamieniony na pusty wynik i log."""
    service, keys = service_pl
    support.load_champion(service, "Ahri", "pl_PL")
    events: list[dict] = []
    service.set_event_sink(events.append)

    def boom(pcm: bytes) -> str:
        raise RuntimeError("model padl")

    service.set_transcriber(boom)
    assert service.feed_pcm(support.silence_pcm(0.2)) == ""
    assert keys.pressed == []
    assert any(event["type"] == "log" and event["level"] == "error" for event in events)


# --- tor z prawdziwymi plikami ----------------------------------------


@pytest.mark.skipif(not ALL_FIXTURES, reason="brak fixture'ow audio, uruchom tests/tools/generate_audio_fixtures.py --smoke")
@pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=lambda f: f.label)
def test_decoded_fixture_drives_the_pipeline(fixture: support.AudioFixture) -> None:
    """MP3 -> PCM 16 kHz -> feed_pcm -> klawisz. Transkrypcja jest znana z manifestu."""
    if support.ffmpeg_binary() is None:
        pytest.skip("brak ffmpeg w PATH")

    pcm = support.decode_pcm(fixture.path)
    assert len(pcm) % 2 == 0, "PCM int16 musi miec parzysta liczbe bajtow"
    seconds = len(pcm) / 2 / 16000
    assert 0.1 < seconds < 8.0, f"podejrzana dlugosc probki: {seconds:.2f} s"

    service, keys = support.make_service(fixture.language)
    support.load_champion(service, fixture.champion, fixture.language)
    service.set_transcriber(lambda buffer: fixture.phrase)

    text = service.feed_pcm(pcm)

    assert text
    assert keys.pressed == [fixture.expected_key], (
        f"{fixture.label} ({fixture.phrase!r}) -> {keys.pressed}, oczekiwano {fixture.expected_key!r}"
    )


@pytest.mark.skipif(not ALL_FIXTURES, reason="brak fixture'ow audio")
def test_manifest_matches_data_dragon() -> None:
    """Frazy w manifescie zgadzaja sie z nazwami umiejetnosci w fixture Data Dragon."""
    import json

    for language in support.available_languages():
        payload = json.loads(support.manifest_path(language).read_text(encoding="utf-8"))
        assert payload["sample_rate"] == 16000
        assert payload["channels"] == 1

        champions = json.loads(
            (support.DDRAGON_DIR / f"championFull.{language}.json").read_text(encoding="utf-8")
        )["data"]
        slots = ["Q", "W", "E", "R"]
        for entry in payload["files"]:
            spells = champions[entry["champion"]]["spells"]
            expected = spells[slots.index(entry["slot"])]["name"]
            assert entry["phrase"] == expected, f"{entry['file']}: {entry['phrase']!r} != {expected!r}"
