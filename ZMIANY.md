# Co się zmieniło

Realizacja `PLAN.md`. Poniżej stan faktyczny: co działa, co zostało zweryfikowane i co musisz zrobić ręcznie.

## Stan plików

Wszystkie pliki są już wgrane bezpośrednio do repozytorium, nie ma nic do rozpakowywania. Strona leży w osobnym katalogu `E:\programowanie\axword-site`.

Zostały trzy rzeczy do zrobienia ręcznie, bo narzędzie zdalne ich nie wykona:

1. Przenieś pliki z `docs/workflows/` do `.github/workflows/` (a `dependabot.yml` do `.github/`). Katalog `.github` jest chroniony przed zapisem zdalnym. W stronie analogicznie: `deploy.yml` z katalogu głównego do `.github/workflows/`.
2. Usuń katalogi `gui/`, `old_files/` i plik `config/config.json`. Są zastąpione, a narzędzie nie umie kasować plików.
3. W `E:\programowanie\axword-site` zrób `git init`, to osobne repozytorium.

Potem:

```
pip install -r requirements.txt -r requirements-dev.txt
cd webui && npm install && npm run build && cd ..
python main.py
```

Panel otworzy się w przeglądarce, nasłuch rusza dopiero po kliknięciu Start.

Zanim wypchniesz cokolwiek na GitHuba, przejrzyj `git status` i `git diff`. Pliki roota, których brakowało w repo przed wgraniem (`main.py`, `build.py`, `README.md`, `version.json`, `installer.iss`, `LoLVoiceAssistant.spec`), zostały odtworzone w nowej wersji.

## Nowa architektura

- `app/` to warstwa wspólna: `paths` (ścieżki per użytkownik), `config` (pydantic + migracja starych plików), `logging_setup` (rotacja, crash dumpy, ZIP z logami), `engines` (rejestr silników i pobieranie modeli), `version`.
- `server/` to lokalne API na `127.0.0.1:21337`: FastAPI, WebSocket ze stanem na żywo, ikona w zasobniku, updater, blokada drugiej instancji, wpis autostartu.
- `webui/` to panel w przeglądarce (Vite + Preact, 260 KB całości, fonty self-hostowane).
- `controller/service.py` to fasada `VoiceService`, przez którą serwer rozmawia z silnikiem. Importuje się bez mikrofonu i bez modelu, dzięki czemu testy chodzą w CI.
- Kontrakt wszystkich interfejsów jest w `docs/CONTRACTS.md`. To jest plik, który trzeba aktualizować przy zmianach.

## Zgodność z Windows

Konfiguracja idzie do `%APPDATA%\LoLVoice`, logi, cache i modele do `%LOCALAPPDATA%\LoLVoice`. Nic nie zapisuje się już do katalogu aplikacji, a stary `config/config.json` jest migrowany przy pierwszym starcie. Instalator jest per użytkownik, bez UAC, z poprawnymi wpisami w Aplikacjach i funkcjach, skrótem do folderu logów i deinstalatorem, który pyta osobno o dane i o pobrane modele.

## Testy

1003 testy, wszystkie zielone, 4 pominięte (rozpoznawanie mowy, bo w kontenerze nie da się pobrać modelu).

- Mapowania: 173 bohaterów razy dwa języki, pełne nazwy Q/W/E/R wracają do właściwego klawisza w 100 procentach przypadków.
- Kolizje: raport `tests/reports/mapping_collisions.json` pokazuje, że skróty jednowyrazowe kolidują u 9 bohaterów po polsku i 11 po angielsku (Orianna, Hwei, Kha'Zix, Aphelios, Ziggs i podobni). Test pilnuje tej listy, więc zmiana patcha to wykryje.
- Mock Live Client API z pełnym meczem i eventami killi, łącznie ze scenariuszem z `PLAN.md`.
- Testy API: autoryzacja, kształt każdej odpowiedzi, zapis ustawień na dysk, ZIP z logami, sprawdzanie aktualizacji na zamockowanym GitHubie.

## Fixture'y audio

Generator `tests/tools/generate_audio_fixtures.py` robi pełny zestaw 1384 plików MP3 z nazwami umiejętności po polsku i angielsku, głosami `pl-PL-MarekNeural` i `en-US-GuyNeural`. Pełny zestaw: `python tests/tools/generate_audio_fixtures.py --all`.

Do repo trafia tylko zestaw smoke: 10 bohaterów, 80 plików, 664 KB. Uwaga: te konkretne pliki zostały wygenerowane offline przez espeak-ng, bo kontener nie ma dostępu do serwerów Microsoftu. Na twoim komputerze i w CI odpali się edge-tts i pliki będą brzmiały jak prawdziwy głos. Przegeneruj je u siebie komendą `python tests/tools/generate_audio_fixtures.py --smoke --force`.

## Naprawione błędy, które były w kodzie

1. Data Dragon nie znajdował 21 bohaterów, bo gra podaje nazwę wyświetlaną (`Wukong`, `Kha'Zix`, `Dr. Mundo`), a Data Dragon kluczuje po identyfikatorze (`MonkeyKing`, `Khazix`, `DrMundo`). Efekt: przy milczącym endpointcie umiejętności ci bohaterowie zostawali bez mapowań.
2. W trybie liter rozmyte dopasowanie liter przechwytywało komendy dodatkowe: `back` wciskało E, `heal` wciskało Q, `powrot` wciskało R. Teraz dokładne trafienie w komendy dodatkowe idzie przed rozmytym dopasowaniem umiejętności.
3. Nieznany tryb rozpoznawania nie dopasowywał niczego poza komendami dodatkowymi.
4. `PUT /settings` z błędną wartością zwracał 500 zamiast 422.
5. Transkrypcja miała zaszyty język polski, więc wybór angielskiego nic nie dawał.

Świadomie zostawione: `app.version.parse` ignoruje sufiksy prerelease. Pipeline wydaje wyłącznie tagi `vX.Y.Z`, więc nie ma czego obsługiwać.

## Co musisz zrobić sam

1. Kupić domenę i podpiąć ją pod Cloudflare Pages. Instrukcja jest w README strony. W `public/CNAME`, `astro.config.mjs` i `robots.txt` wpisane jest `axword.com`.
2. Ustawić sekrety w GitHubie: `CLOUDFLARE_API_TOKEN` i `CLOUDFLARE_ACCOUNT_ID` dla strony, opcjonalnie `WINGET_TOKEN` dla wingeta. Bez wingeta workflow po prostu nic nie robi.
3. Pierwszy manifest do wingeta trzeba wysłać ręcznie przez `wingetcreate new`, pipeline umie tylko `update`.
4. Uzupełnić sumy kontrolne modeli: `python tools/refresh_engine_checksums.py --all`. Teraz `sha256` jest `null`, czyli pobieranie modeli nie jest weryfikowane.
5. Podmienić adres kontaktowy na stronie, w `src/i18n/strings.ts` jest placeholder.
6. Podpis kodu: aplikacja jest niepodpisana, więc SmartScreen ostrzeże. Winget i stała nazwa pliku instalatora to łagodzą, docelowo warto rozważyć certyfikat.
