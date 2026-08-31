"""E2E z prawdziwym Whisperem: MP3 -> PCM -> model -> mapowanie -> klawisz.

Dwa poziomy, zgodnie z PLAN.md 6.2:

* smoke  (marker audio): zacommitowany zestaw 10 bohaterow, prog 80% trafien
  liczony na jezyk, bo tiny nie jest deterministycznie idealny;
* full   (markery audio i slow): wszystko, co lezy w tests/fixtures/audio,
  bez progu, sluzy do zbierania raportu w nocnym przebiegu.

Oba poziomy zapisuja tests/reports/recognition_report.json (sciezke da sie
nadpisac przez LOLVOICE_AUDIO_REPORT). Nocny workflow wysyla ten plik jako
artefakt i czyta z niego pole "accuracy".

Gdy nie ma zadnego backendu Whispera albo modelu, testy pomijaja sie z
komunikatem mowiacym, czego brakuje. Brak modelu nie moze wywracac CI.
"""

from __future__ import annotations

import os

import audio_support as support
import pytest

pytestmark = pytest.mark.audio

SMOKE_ACCURACY = float(os.environ.get("LOLVOICE_SMOKE_ACCURACY", "0.8"))

SMOKE_CHAMPIONS = (
    "Ahri",
    "Aatrox",
    "Jinx",
    "Lux",
    "Yasuo",
    "Zed",
    "Garen",
    "Katarina",
    "Thresh",
    "Hwei",
)


# --- wspolne zasoby ---------------------------------------------------


@pytest.fixture(scope="session")
def transcriber():
    """Zaladowany model albo skip z powodem."""
    if support.ffmpeg_binary() is None:
        pytest.skip("brak ffmpeg w PATH, nie da sie zdekodowac fixture'ow MP3")

    ready, reason = support.whisper_status()
    if not ready:
        pytest.skip(f"rozpoznawanie mowy niedostepne: {reason}")

    try:
        return support.load_transcriber()
    except Exception as exc:  # brak pliku modelu, zla wersja backendu
        pytest.skip(f"nie udalo sie zaladowac modelu: {exc}")


@pytest.fixture(scope="session")
def collector(transcriber):
    """Zbiera wyniki calej sesji i zapisuje raport na koniec."""
    report = support.ReportCollector(
        tier=os.environ.get("LOLVOICE_AUDIO_TIER", "smoke"),
        engine=f"{transcriber.engine_id} ({transcriber.backend})",
    )
    yield report
    if report.results:
        path = report.write()
        print(f"\nRaport rozpoznawania: {path} (accuracy {report.as_dict()['accuracy']:.3f})")


def _run(fixtures, transcriber, collector) -> float:
    """Puszcza liste fixture'ow przez pelny tor i zwraca accuracy."""
    if not fixtures:
        pytest.skip("brak fixture'ow audio, uruchom tests/tools/generate_audio_fixtures.py --smoke")

    language = fixtures[0].language
    collector.fixture_engine = support.fixture_engine(language)
    service, keys = support.make_service(language)
    current: str | None = None

    for fixture in fixtures:
        if fixture.champion != current:
            support.load_champion(service, fixture.champion, fixture.language)
            current = fixture.champion

        keys.reset()
        pcm = support.decode_pcm(fixture.path)
        heard = transcriber.transcribe_pcm(pcm, fixture.language)
        matched = service.handle_transcript(heard) if heard else None

        collector.add(
            support.Result(
                language=fixture.language,
                champion=fixture.champion,
                slot=fixture.slot,
                phrase=fixture.phrase,
                heard=heard,
                expected_key=fixture.expected_key,
                matched=matched if isinstance(matched, str) else None,
            )
        )

    return collector.accuracy_for(language)


def _smoke_fixtures(language: str) -> list[support.AudioFixture]:
    return [f for f in support.load_fixtures(language) if f.champion in SMOKE_CHAMPIONS]


# --- poziom smoke -----------------------------------------------------


@pytest.mark.parametrize("language", support.LANGUAGES)
def test_smoke_accuracy(language: str, transcriber, collector) -> None:
    """Zacommitowany zestaw 10 bohaterow, prog 80% trafien na jezyk."""
    fixtures = _smoke_fixtures(language)
    if not fixtures:
        pytest.skip(
            f"brak fixture'ow audio dla {language}, "
            "uruchom python tests/tools/generate_audio_fixtures.py --smoke"
        )

    accuracy = _run(fixtures, transcriber, collector)
    misses = [r for r in collector.results if r.language == language and not r.ok]
    details = "\n".join(
        f"  {r.champion}/{r.slot}: oczekiwano {r.expected_key} dla {r.phrase!r}, "
        f"uslyszano {r.heard!r} -> {r.matched}"
        for r in misses[:15]
    )
    assert accuracy >= SMOKE_ACCURACY, (
        f"{language}: accuracy {accuracy:.2%} ponizej progu {SMOKE_ACCURACY:.0%} "
        f"({len(misses)} bledow z {collector.count_for(language)})\n{details}"
    )


# --- poziom pelny -----------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("language", support.LANGUAGES)
def test_full_corpus(language: str, transcriber, collector) -> None:
    """Wszystko, co lezy w tests/fixtures/audio. Bez progu, liczy sie raport."""
    if os.environ.get("LOLVOICE_AUDIO_TIER", "smoke") != "full" and not os.environ.get("CI"):
        pytest.skip("poziom pelny: ustaw LOLVOICE_AUDIO_TIER=full albo uruchom w CI")

    fixtures = support.load_fixtures(language)
    if not fixtures:
        pytest.skip(
            f"brak fixture'ow audio dla {language}, "
            "uruchom python tests/tools/generate_audio_fixtures.py --all"
        )

    collector.tier = "full"
    accuracy = _run(fixtures, transcriber, collector)
    print(f"\n{language}: accuracy {accuracy:.2%} na {len(fixtures)} probkach")
    assert collector.count_for(language) == len(fixtures)
