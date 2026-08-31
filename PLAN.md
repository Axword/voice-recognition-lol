# PLAN PRZEBUDOWY: LoL Voice Controller

Dokument dla agenta implementującego. Opisuje docelową architekturę, zakres prac, kolejność faz i kryteria akceptacji. Repo: `E:\programowanie\lolarena` (GitHub: `Axword/voice-recognition-lol`).

Zasada nadrzędna dla całego UI i strony: żadnego "AI slopu". Bez długich myślników (em dash), bez emoji w interfejsie, bez gradientowych hero-sekcji z fioletem, bez wygenerowanych stockowych ilustracji, bez pustych frazesów typu "Unleash the power of". Prosto, schludnie, konkretnie. Wzorce: Postman (gęste, funkcjonalne UI), claude.ai / Anthropic (spokojna typografia, dużo światła, stonowana paleta), aplikacje Apple (hierarchia, ograniczona liczba elementów na ekranie).

---

## 1. Stan obecny (kontekst dla agenta)

Aplikacja w Pythonie: rozpoznawanie mowy Whisper (pywhispercpp / faster-whisper / openai-whisper z fallbackiem), VAD (webrtcvad), wciskanie klawiszy (pynput), wykrywanie bohatera przez Live Client Data API (`https://127.0.0.1:2999/liveclientdata/...`), nazwy umiejętności z Riot Data Dragon (`championFull.json`, wersje pl_PL i en_US). GUI w tkinterze (`gui/lol_voice_gui.py`, 47 KB, do wymiany). Build: PyInstaller + Inno Setup, workflow GitHub Actions istnieje, ale używa przestarzałych akcji (actions/checkout@v3, upload-artifact@v3, create-release@v1) i nie ma w nim testów. Konfiguracja i cache pisane do katalogu roboczego aplikacji (do naprawy, patrz sekcja 5).

Decyzje podjęte z użytkownikiem:

- Panel ustawień: lokalne API + interfejs w przeglądarce.
- Strona publiczna: prawdziwa domena (axword.com lub axword.pl, do kupienia), pomyślana jako osobisty hub, na którym w przyszłości będzie więcej aplikacji. Strona projektu LoL Voice jest podstroną tego hubu. Kod strony trzymany w osobnych plikach, niezależnie od kodu aplikacji.
- Architektura desktop: aplikacja w zasobniku systemowym (tray) + panel w przeglądarce (domyślna rekomendacja, użytkownik nie wskazał inaczej).
- Dystrybucja: Inno Setup per-user + publikacja w winget + auto-update przez GitHub Releases (domyślna rekomendacja).

---

## 2. Architektura docelowa

```
┌────────────────────────────┐         ┌──────────────────────────┐
│  Aplikacja desktop (tray)  │         │  Przeglądarka użytkownika │
│                            │  HTTP   │                          │
│  FastAPI (127.0.0.1:21337) │◄───────►│  Panel ustawień (SPA/    │
│  ├─ REST: /api/v1/...      │   WS    │  statyczny frontend      │
│  ├─ WebSocket: /ws/status  │         │  serwowany przez FastAPI)│
│  ├─ Silnik głosowy         │         └──────────────────────────┘
│  │  (obecny controller)    │
│  ├─ Live Client API poller │         ┌──────────────────────────┐
│  └─ Updater                │         │  axword.com (GitHub      │
└────────────────────────────┘         │  Pages + custom domain)  │
                                       │  hub + /lol-voice        │
                                       └──────────────────────────┘
```

### 2.1 Backend lokalny (nowy moduł `server/`)

- FastAPI + uvicorn wbudowane w aplikację, nasłuch wyłącznie na `127.0.0.1`, stały port 21337 z fallbackiem na wolny port (port zapisywany do pliku `%LOCALAPPDATA%\LoLVoice\runtime.json`, żeby panel i skróty wiedziały gdzie się łączyć).
- Zabezpieczenie: token sesyjny generowany przy starcie, dołączany do URL otwieranego w przeglądarce (`http://127.0.0.1:21337/?token=...`), sprawdzany w middleware. CORS zamknięty do własnego origin. To wystarcza dla localhost, bez kont i haseł.
- Tray (pystray lub natywnie przez pywin32): ikona z menu: Otwórz panel, Start/Stop nasłuchu, Otwórz folder logów, Sprawdź aktualizacje, Zamknij. Pojedyncza instancja (mutex Windows), druga próba uruchomienia otwiera panel istniejącej.
- Obecna logika (`controller/`, `game/`, `controls/`) zostaje, ale odcinamy ją od tkintera i konfigurujemy przez warstwę API. Tkinter i `gui/` przenieść do `old_files/` po osiągnięciu parytetu funkcji.

### 2.2 REST API (kontrakt dla frontu)

Wersjonowane pod `/api/v1`:

- `GET /status` : stan (nasłuch on/off, bohater, tryb, backend STT, wersja aplikacji, liczba komend).
- `POST /listening/start`, `POST /listening/stop` : przycisk Start w UI uruchamia nasłuch (wymaganie użytkownika: aplikacja włącza nasłuch po kliknięciu w panelu, nie automatycznie).
- `GET /settings`, `PUT /settings` : pełna konfiguracja (język rozpoznawania, język UI, tryb rozpoznawania letters/spells, czułość, klawisz flash, urządzenie audio, silnik STT, model, autostart z Windows, autostart nasłuchu).
- `GET /engines` : lista silników STT z informacją: zainstalowany / do pobrania, rozmiar, szybkość, jakość (sekcja 6).
- `POST /engines/{id}/download` : pobranie modelu z paskiem postępu (progres przez WebSocket).
- `GET /champions/{name}/mappings` : podgląd aktualnych mapowań głosowych dla bohatera (do zakładki "Komendy" w panelu).
- `GET /logs` : lista plików logów; `GET /logs/download` : ZIP wszystkich logów jako attachment (sekcja 8).
- `GET /audio/devices` : lista mikrofonów; `POST /audio/test` : 3-sekundowy test mikrofonu ze zwróconym poziomem sygnału i transkrypcją (kluczowe dla user-friendly onboardingu).
- `GET /update/check`, `POST /update/install` (sekcja 9).
- `WS /ws/status` : push stanu w czasie rzeczywistym: nasłuch, bohater, ostatnio usłyszany tekst, dopasowana komenda, poziom mikrofonu, postęp pobierania modeli.

### 2.3 Frontend panelu (nowy katalog `webui/`)

- Vite + vanilla TypeScript lub Preact (bez Reacta z routerem i bez ciężkich UI kitów, panel ma być mały i szybki). Build do statycznych plików serwowanych przez FastAPI (`StaticFiles`), więc zero Node w runtime u użytkownika.
- Ekrany: Pulpit (status + wielki przycisk Start/Stop + ostatnio rozpoznane frazy na żywo), Ustawienia (formularz z auto-zapisem), Silniki STT (karty z przyciskiem Pobierz i postępem), Komendy (tabela mapowań dla aktualnego bohatera, z wyszukiwarką), Logi (podgląd ogona loga na żywo + przycisk Pobierz ZIP), O aplikacji (wersja, sprawdź aktualizacje).
- i18n: pl i en, przeniesione z `gui/translations.py` do plików JSON współdzielonych przez panel.

---

## 3. Strona publiczna axword.com (osobne repo `axword-site`)

Osobne repozytorium, osobny deploy, zero zależności od kodu aplikacji.

- Stack: Astro albo czysty HTML+CSS z małą ilością JS (rekomendacja: Astro, bo hub będzie rósł o kolejne aplikacje; każda aplikacja to wpis w kolekcji treści). Hosting: GitHub Pages albo Cloudflare Pages (rekomendacja: Cloudflare Pages, darmowy, łatwe podpięcie kupionej domeny, automatyczny deploy z gita).
- Struktura: strona główna = wizytówka Axword + siatka "Moje aplikacje" (na start jedna karta: LoL Voice). Podstrona `/lol-voice`: opis w 2 zdaniach, krótkie wideo/gif z działania, przycisk pobierania, sekcja FAQ, link do GitHub.
- Przycisk pobierania: JS pobiera `https://api.github.com/repos/Axword/voice-recognition-lol/releases/latest` i podstawia bezpośredni link do instalatora + numer wersji. Fallback: link do strony Releases.
- Domena: użytkownik kupuje axword.com lub axword.pl (rekomendacja: .com jako główna, .pl jako przekierowanie, jeśli budżet pozwala). W planie tylko instrukcja podpięcia DNS (CNAME na Pages), zakup robi użytkownik ręcznie.

### 3.1 Design system (wspólny dla strony i panelu ustawień)

Jeden plik tokenów CSS (custom properties) kopiowany do obu projektów:

- Motywy: ciemny jest domyślny i pierwszoplanowy (wymaganie), jasny jako alternatywa, przełącznik + respektowanie `prefers-color-scheme`.
- Paleta ciemna: tła w okolicach `#111214` / `#1a1b1e`, tekst `#e8e6e3`, obramowania `#2a2c30`, jeden kolor akcentu, np. zielony `#3ecf8e` albo bursztyn `#e8a33d` (jeden, nie tęcza). Paleta jasna: tło `#faf9f7` (ciepła biel w stylu Anthropic), tekst `#1f1e1d`.
- Typografia (wymaganie: ciekawa, nietypowa czcionka): nagłówki **Bricolage Grotesque**, tekst **Instrument Sans**, kod i dane **JetBrains Mono**. Alternatywa, jeśli Bricolage nie zagra: Space Grotesk + Inter. Fonty self-hostowane (woff2 w repo), bez Google Fonts CDN.
- Zasady: dużo światła, max szerokość treści ~68ch, subtelne obramowania zamiast cieni, brak animacji poza krótkimi przejściami 150ms, ikony Lucide (outline, spójny zestaw), zaokrąglenia 8px.
- Zakaz w tekstach: długi myślnik (em dash), pisownia Title Case W Każdym Słowie, wykrzykniki w copy, buzzwordy. Interpunkcja: przecinki, dwukropki, zwykły dywiz.

---

## 4. Wybór silników STT, łatwe pobieranie (wymaganie)

Użytkownik ma wybierać silnik w panelu i pobierać go jednym kliknięciem.

- Rejestr silników w `data/engines.json`, każdy wpis: id, nazwa, opis jednym zdaniem, backend (pywhispercpp / faster-whisper), model, rozmiar pliku, URL pobierania, SHA256, orientacyjna szybkość i jakość (etykiety: Szybki / Zbalansowany / Dokładny).
- Minimalny zestaw na start:
  - `whisper-tiny` (ggml, ~75 MB): Szybki, domyślny, dołączony do instalatora.
  - `whisper-base` (ggml, ~140 MB): Zbalansowany, do pobrania.
  - `whisper-small` (ggml, ~460 MB): Dokładny, do pobrania.
  - `faster-whisper-small` (CTranslate2): wariant GPU, pokazywany tylko gdy wykryto CUDA.
- Pobieranie: do `%LOCALAPPDATA%\LoLVoice\models\`, wznawialne (Range), weryfikacja SHA256, postęp przez WebSocket, przycisk Anuluj. Zmiana silnika bez restartu aplikacji (przeładowanie modelu w tle, w tym czasie nasłuch zatrzymany z komunikatem).
- Usunięcie twardej ścieżki `models/ggml-tiny.bin` z `lol_whisp_controller.py`, ścieżka i backend przychodzą z konfiguracji.

---

## 5. Zgodność z zasadami Windows (wymaganie)

- Wszystkie zapisy poza katalog instalacji: konfiguracja `%APPDATA%\LoLVoice\config.json`, logi `%LOCALAPPDATA%\LoLVoice\logs\`, cache Data Dragon `%LOCALAPPDATA%\LoLVoice\cache\`, modele `%LOCALAPPDATA%\LoLVoice\models\`. Migracja przy pierwszym starcie: jeśli istnieje stary `config/config.json`, przenieś. Obecny kod pisze do cwd, to jest bug do naprawy w całym repo (`mapping_manager`, `lol_data_manager`, logger).
- Instalator Inno Setup: instalacja per-user (`PrivilegesRequired=lowest`, do `{localappdata}\Programs\LoLVoice`), bez UAC, poprawne wpisy w Aplikacje i funkcje (nazwa, wydawca Axword, wersja, ikona, szacowany rozmiar), czysty deinstalator z pytaniem czy usunąć dane i modele, skrót w Menu Start (bez wymuszania skrótu na pulpicie).
- Autostart z Windows przez wpis w `HKCU\...\Run` (opcja w ustawieniach, domyślnie wyłączona). Autostart uruchamia tylko tray, nasłuch startuje dopiero po kliknięciu w panelu, chyba że użytkownik włączy opcję "startuj nasłuch automatycznie".
- Manifest exe: `longPathAware`, DPI awareness per-monitor v2, poprawne metadane wersji (FileVersion, ProductName, CompanyName), ikona.
- Podpisywanie kodu: na razie brak certyfikatu. Mitygacja SmartScreen: spójna nazwa pliku między wydaniami, publikacja w winget (manifest w `microsoft/winget-pkgs`, automatyczne PR-y nowych wersji przez `wingetcreate` w pipeline). W przyszłości ewentualnie certyfikat Azure Trusted Signing (tanie, ~10 USD/mies), zostawić TODO w pipeline.
- Zero zapisu do rejestru poza wpisem Run i wpisami instalatora.

---

## 6. Testy (wymaganie, szczegółowo)

Katalog `tests/`, pytest, uruchamiane w CI na Windows i Ubuntu.

### 6.1 Testy jednostkowe i integracyjne z mockami LoL

Źródło prawdy o nazwach umiejętności: Data Dragon `championFull.json` (pl_PL i en_US), pobrany raz i zapisany jako fixture w `tests/fixtures/ddragon/` (wersja przypięta, np. z pola w `tests/fixtures/VERSION`). To jest to samo źródło, z którego korzysta wiki LoL, a jest stabilnym API. Skrypt `tests/tools/refresh_fixtures.py` odświeża fixture do najnowszego patcha.

- **Mock Live Client Data API**: klasa `FakeLiveClient` (respx albo pytest-httpserver na porcie testowym) serwująca `/liveclientdata/activeplayer`, `/liveclientdata/playerlist`, `/liveclientdata/eventdata`. Generator odpowiedzi buduje realistyczne payloady dla każdego bohatera z fixture, w tym eventy z killami: `ChampionKill` z polami KillerName/VictimName oraz `Multikill`. Test parametryzowany po wszystkich ~170 bohaterach: aplikacja wykrywa bohatera, buduje mapowania i dla każdej nazwy umiejętności (Q/W/E/R, plus sub-umiejętności typu Hwei) `match_command(nazwa)` zwraca właściwy klawisz.
- **Testy mapowań**: normalizacja polskich znaków, warianty częściowe (pojedyncze słowa nazwy), kolizje nazw między umiejętnościami jednego bohatera (raport kolizji jako test, żeby wiedzieć którzy bohaterowie są problematyczni), tryb letters vs spells, komendy specjalne (flash, escape, random, comba).
- **Testy API**: httpx TestClient na FastAPI: start/stop nasłuchu (z podmienionym kontrolerem-atrapą, bez mikrofonu), zapis/odczyt ustawień, autoryzacja tokenem, download logów zwraca poprawny ZIP.
- **Test scenariusza kill**: FakeLiveClient emituje sekwencję eventów (GameStart, ChampionKill gracza), test sprawdza że stan gry w `/status` i logika mapowań reagują poprawnie (bohater wykryty, mapowania załadowane przed killem, brak crasha przy nietypowych nazwach graczy).

### 6.2 Fixture'y audio MP3 (wymaganie)

Krótkie MP3, w których głos bota wypowiada każdą nazwę umiejętności po polsku i po angielsku. Służą jako testy end-to-end rozpoznawania.

- Generator `tests/tools/generate_audio_fixtures.py`: TTS przez **edge-tts** (darmowe, głosy `pl-PL-MarekNeural` i `en-US-GuyNeural`), wejście: fixture Data Dragon, wyjście: `tests/fixtures/audio/{lang}/{champion}/{slot}.mp3`, mono 16 kHz, przycięte z ciszy, ~1-2 s każdy. Pełny zestaw to około 170 bohaterów x 4+ umiejętności x 2 języki, czyli ~1400 plików rzędu 15-20 MB łącznie.
- Przechowywanie: NIE commitować do repo. Generowane w CI i cache'owane po kluczu (wersja patcha + wersja skryptu) przez `actions/cache`; lokalnie generowane na żądanie tym samym skryptem.
- **Test e2e rozpoznawania**: pipeline testowy dekoduje MP3 do PCM 16 kHz (pydub/ffmpeg), podaje bufor bezpośrednio do `_process_whisper_audio` (z pominięciem mikrofonu i VAD), i sprawdza, że rozpoznany tekst dopasowuje się do właściwego klawisza danego bohatera.
- Dwa poziomy w CI: **smoke** (na każdy PR): 10 stałych bohaterów x 2 języki na modelu tiny, próg zaliczenia co najmniej 80% trafień (Whisper tiny nie jest deterministycznie idealny, test mierzy accuracy zamiast wymagać 100%). **Pełny przebieg** (nightly): wszyscy bohaterowie, wynik zapisywany jako artefakt `recognition_report.json` z accuracy per bohater i per język; regresja accuracy poniżej progu z poprzedniego przebiegu oznacza fail. Ten raport jest też złotem dla produktu: pokazuje, dla których bohaterów warto dodać aliasy.

---

## 7. CI/CD na GitHubie (wymaganie: aplikacja tworzy się w pipeline)

Przebudowa `.github/workflows/`:

- **`ci.yml`** (każdy PR i push): lint (ruff), testy jednostkowe + API na windows-latest i ubuntu-latest, build frontendu `webui/`, smoke testy audio (z cache fixture'ów). Bez artefaktów wydania.
- **`build-release.yml`** (tag `v*` oraz ręczny dispatch z wyborem major/minor/patch): buduje na windows-latest exe (PyInstaller, onedir), instalator Inno Setup, portable ZIP; generuje `latest.json` (wersja, url instalatora, sha256) jako plik manifestu dla updatera; tworzy GitHub Release z changelogiem. Aktualizacja przestarzałych akcji: checkout@v4, setup-python@v5, upload-artifact@v4, softprops/action-gh-release zamiast martwego create-release@v1. Usunąć hack "Create icon if missing" (ikony są w repo).
- **`nightly.yml`**: pełny przebieg testów audio + raport accuracy.
- **`winget.yml`** (po publikacji release): `wingetcreate update` i PR do winget-pkgs.
- Strona axword.com ma własny pipeline w swoim repo (build Astro + deploy na Pages).
- Wersjonowanie: jedno źródło `version.json`, tag tworzy release, koniec z auto-bump na każdy push do main (obecny workflow robi release z każdego pusha, to do zmiany: release tylko z tagu lub ręcznego dispatchu).

---

## 8. Logi dostępne z frontu bez działającego serwera (wymaganie)

Interpretacja: pobieranie logów nie może zależeć od żadnego zewnętrznego serwera, a dostęp do logów musi istnieć nawet wtedy, gdy lokalne API padło (bo właśnie wtedy logi są najbardziej potrzebne).

- Ścieżka podstawowa: przycisk "Pobierz logi (ZIP)" w panelu, `GET /logs/download`, czysto lokalne.
- Ścieżka awaryjna 1: pozycja "Otwórz folder logów" w menu tray (działa niezależnie od API).
- Ścieżka awaryjna 2: skrót "Logi LoL Voice" w Menu Start instalowany przez Inno Setup, wskazujący na `%LOCALAPPDATA%\LoLVoice\logs\` (działa nawet gdy aplikacja w ogóle się nie uruchamia).
- Logi: `logging` z RotatingFileHandler (5 plików po 2 MB), format z timestampem, poziomami i nazwą modułu; crash handler zapisujący traceback do osobnego `crash-YYYYMMDD-HHMMSS.log`. ZIP z logami zawiera też `system-info.txt` (wersja aplikacji, Windows, Python, wykryty backend STT) dla łatwiejszego debugowania zgłoszeń.

---

## 9. Aktualizacje aplikacji (wymaganie)

- Przy starcie (i raz na 24h, oraz na żądanie z panelu) aplikacja pobiera `latest.json` z assetów najnowszego GitHub Release i porównuje wersję.
- Jeśli jest nowsza: nienachalny banner w panelu i kropka na ikonie tray, przycisk "Zaktualizuj". Kliknięcie: pobranie instalatora do temp, weryfikacja sha256, zamknięcie aplikacji i uruchomienie `Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, instalator per-user podmienia pliki i restartuje aplikację (flaga w Inno: `[Run] ... postinstall`).
- Żadnych wymuszonych aktualizacji, opcja "pomiń tę wersję" w ustawieniach. Kanał drugi: winget upgrade dla użytkowników winget.

---

## 10. Kolejność realizacji (fazy dla agenta)

Każda faza kończy się zielonym CI i działającą aplikacją.

**Faza 0, porządki (0.5 dnia):** naprawa ścieżek zapisu na AppData/LocalAppData, RotatingFileHandler, usunięcie duplikatów z `requirements.txt` (torch jest 2x, torchvision niepotrzebne), rozdzielenie requirements na core/dev, wyniesienie martwego kodu do `old_files/`, aktualizacja akcji w istniejącym workflow, dodanie ruff.

**Faza 1, testy zanim ruszymy architekturę (1-2 dni):** fixture Data Dragon, FakeLiveClient, testy mapowań dla wszystkich bohaterów, testy scenariusza kill, `ci.yml`. To siatka bezpieczeństwa na refactor.

**Faza 2, backend API + tray (2-3 dni):** moduł `server/`, kontrakt z sekcji 2.2, tray, pojedyncza instancja, token, start nasłuchu wyłącznie z API/tray. Tkinter jeszcze działa równolegle.

**Faza 3, panel webowy (2-3 dni):** `webui/` z design systemem (tokeny, ciemny tryb domyślny, Bricolage Grotesque + Instrument Sans + JetBrains Mono), wszystkie ekrany z sekcji 2.3, WebSocket na żywo. Po parytecie funkcji: usunięcie tkintera z buildu.

**Faza 4, silniki STT i pobieranie modeli (1-2 dni):** rejestr silników, downloader z postępem i sumami kontrolnymi, przeładowanie modelu bez restartu.

**Faza 5, fixture'y MP3 i testy e2e (1-2 dni):** generator edge-tts, cache w CI, smoke na PR, pełny nightly z raportem accuracy.

**Faza 6, instalator, updater, winget (1-2 dni):** nowy skrypt Inno per-user, skrót do logów, manifest exe, `latest.json`, updater w aplikacji, `winget.yml`, przebudowany `build-release.yml` (release tylko z tagów).

**Faza 7, strona axword.com (1-2 dni, osobne repo):** szkielet Astro z kolekcją aplikacji, strona główna hubu, podstrona `/lol-voice` z pobieraniem z GitHub API, deploy na Cloudflare Pages, instrukcja DNS dla kupionej domeny.

---

## 11. Kryteria akceptacji (checklista końcowa)

1. Świeży Windows: instalacja bez uprawnień admina, aplikacja startuje do tray, panel otwiera się w przeglądarce, nasłuch rusza dopiero po kliknięciu Start.
2. Zmiana ustawień w panelu działa bez restartu; zmiana silnika STT pobiera model z postępem i przełącza bez restartu.
3. `pytest` zielony lokalnie i w CI; testy mapowań przechodzą dla wszystkich bohaterów w pl i en; smoke audio co najmniej 80% trafień; nightly generuje raport accuracy.
4. Tag `vX.Y.Z` produkuje w pipeline instalator, portable ZIP i `latest.json` w GitHub Release bez ręcznych kroków.
5. Starsza wersja aplikacji wykrywa nowy release i aktualizuje się jednym kliknięciem.
6. Logi osiągalne trzema drogami: przycisk w panelu, menu tray, skrót w Menu Start, bez internetu.
7. Panel i strona przechodzą przegląd wizualny: ciemny tryb domyślny, brak em dash w całym copy (test CI grepujący `—` w plikach UI i strony), fonty self-hostowane, jeden kolor akcentu.
8. Strona na domenie użytkownika pokazuje aktualną wersję i działający link pobierania z GitHub Releases.

---

## 12. Poza zakresem (świadomie)

Podpisywanie kodu certyfikatem (TODO na później), wersja macOS/Linux panelu (kod tego nie blokuje, ale nie testujemy), Microsoft Store/MSIX, konta użytkowników i telemetria (nie zbieramy nic), tłumaczenia poza pl/en.
