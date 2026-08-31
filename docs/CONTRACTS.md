# Kontrakty wewnętrzne

Wspólny punkt odniesienia dla wszystkich modułów. Zmiana czegokolwiek tutaj wymaga aktualizacji tego pliku.

## Układ repozytorium

```
app/          warstwa wspólna: paths, config, logging_setup, version, engines
controller/   silnik głosowy (Whisper + VAD)
controls/     mapowania komend, wciskanie klawiszy
game/         Live Client Data API, Data Dragon, mapowanie umiejętności
server/       FastAPI, WebSocket, tray, updater, single instance
webui/        panel ustawień (Vite, build do webui/dist)
tests/        pytest, fixture'y, narzędzia generujące
docs/         ten plik i pochodne
```

## app.paths

`CONFIG_DIR`, `DATA_DIR`, `CONFIG_FILE`, `LOG_DIR`, `CACHE_DIR`, `MODELS_DIR`, `RUNTIME_FILE`, `ensure_dirs()`, `bundled_dir()`, `refresh()`.
Zmienna środowiskowa `LOLVOICE_HOME` przekierowuje wszystko do jednego katalogu (używane w testach i w trybie portable).
Nic nie zapisuje do katalogu instalacji.

## app.config

`Settings` (pydantic) z polami: `recognition_mode`, `spell_sensitivity`, `language`, `merge_command_languages`, `ui_language`, `flash_key`, `summoner2_key`, `engine_id`, `audio_device`, `start_with_windows`, `start_listening_on_launch`, `theme`, `skipped_version`, `check_updates`.
Komendy dodatkowe i warianty liter zyja w `controls/command_languages.py`, po slowniku na jezyk; aktywny jest slownik biezacego jezyka, a `merge_command_languages` laczy wszystkie.
Funkcje: `load(force=False)`, `save(settings)`, `update(patch: dict)`, `reset_cache()`.
Migracja ze starych `config/config.json` i `config.json` dzieje się przy pierwszym `load()`.

## app.logging_setup

`setup(debug)`, `get_logger(name)`, `tail(limit)`, `install_crash_handler()`, `system_info()`, `build_log_archive() -> bytes`.

## app.engines

`list_engines()`, `get(id)`, `resolve_active()`, `download(id, progress)`, `cancel_download(id)`, `remove(id)`.
Rejestr w `data/engines.json`.

## controller.service.VoiceService

Fasada, przez którą serwer rozmawia z silnikiem głosowym. Singleton: `get_service() -> VoiceService`.
Konstruktor nie dotyka mikrofonu ani modelu, więc importuje się w testach i w CI bez sprzętu audio.

| Metoda | Zachowanie |
| --- | --- |
| `start()` | ładuje model (jeśli trzeba) i uruchamia nasłuch, idempotentne, zwraca `bool` |
| `stop()` | zatrzymuje nasłuch i zwalnia strumień audio |
| `status()` | dict zgodny z `GET /status` |
| `apply_settings(settings)` | przebudowa mapowań, ewentualne przeładowanie silnika w tle |
| `reload_engine()` | przeładowanie modelu bez restartu procesu |
| `mappings()` | `[{phrase, key, source}]` dla aktualnego trybu i bohatera |
| `list_audio_devices()` | `[{id, name, default}]` |
| `test_microphone(seconds=3)` | `{level: float 0..1, transcript: str}` |
| `set_event_sink(fn)` | `fn(event: dict)` wołane dla `heard`, `status`, `log` |
| `feed_pcm(pcm: bytes)` | wstrzyknięcie surowego PCM 16 kHz mono, ścieżka testów e2e, zwraca rozpoznany tekst |

Poza tabelą:

| Metoda | Zachowanie |
| --- | --- |
| `set_transcriber(fn)` | podmienia transkrypcję, `fn(pcm: bytes) -> str`, `None` przywraca Whispera. Równoważne ustawieniu `service._transcriber`. Tego używają testy e2e |
| `handle_transcript(text)` | wspólna ścieżka komend dla `feed_pcm` i dla żywego audio, zwraca dopasowany klawisz albo `None` |
| `set_update_available(flag)` | updater ustawia flagę widoczną w `/status` |
| `reset_service()` | funkcja modułu, kasuje singleton, dla testów przestawiających `LOLVOICE_HOME` |

`status()` zawiera dodatkowo klucz `error`: ostatni błąd startu silnika albo `null`.
Zdarzenie `heard` ma kształt `{type, text, matched, time}`, gdzie `matched` to klawisz albo `null`.

## REST API (prefiks `/api/v1`, nasłuch tylko na 127.0.0.1)

Autoryzacja: nagłówek `X-Auth-Token` albo `?token=`. Token generowany przy starcie, zapisany w `RUNTIME_FILE`, wstrzykiwany do HTML panelu.

| Metoda | Ścieżka | Odpowiedź |
| --- | --- | --- |
| GET | `/status` | `{listening, game_active, champion, mode, engine_id, engine_name, version, mappings_count, last_command, last_heard, update_available}` |
| POST | `/listening/start` \| `/listening/stop` | `{listening}` |
| GET | `/settings` | pełny `Settings` |
| PUT | `/settings` | częściowy patch, zwraca pełny `Settings` |
| GET | `/engines` | `{engines: [...]}` |
| POST | `/engines/{id}/download` | `{started: true}`, postęp leci po WS |
| POST | `/engines/{id}/cancel` | `{cancelled: true}` |
| POST | `/engines/{id}/activate` | `{engine_id}` |
| GET | `/audio/devices` | `{devices: [{id, name, default}]}` |
| POST | `/audio/test` | `{level, transcript}` |
| GET | `/champions/current/mappings` | `{champion, mode, mappings: [{phrase, key, source}]}` |
| GET | `/logs` | `{files: [{name, size, modified}], tail: [...]}` |
| GET | `/logs/download` | ZIP (`Content-Disposition: attachment`) |
| GET | `/update/check` | `{current, latest, available, url, notes}` |
| POST | `/update/install` | `{started: bool, reason?}` |
| POST | `/app/quit` | `{ok: true}` |

WebSocket `/ws/status`: ramki `{type, ...}`, gdzie `type` należy do `status`, `heard`, `download`, `log`, `update`.

## Zasady copy i UI

Ciemny motyw domyślny. Jeden kolor akcentu. Bez emoji w interfejsie. Bez długiego myślnika (`—`) i bez półpauzy w roli myślnika w jakimkolwiek tekście widocznym dla użytkownika: w CI jest test, który to wykrywa. Bez wykrzykników w copy. Zdania krótkie, konkretne.

Fonty self-hostowane w `webui/public/fonts`: Bricolage Grotesque (nagłówki), Instrument Sans (tekst), JetBrains Mono (dane).

Tokeny kolorów (CSS custom properties, ta sama nazwa w panelu i na stronie):

```
--bg          #111214 / jasny #faf9f7
--surface     #17181b / jasny #ffffff
--border      #2a2c30 / jasny #e6e3de
--text        #e8e6e3 / jasny #1f1e1d
--text-muted  #9a9894 / jasny #6b6862
--accent      #3ecf8e
--danger      #e5644e
--radius      8px
```
