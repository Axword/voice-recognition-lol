# Docker

Kontenery sluza do pracy nad panelem, API i testami. Nie zastepuja aplikacji na Windowsie.

## Co dziala, a co nie

| Funkcja | W kontenerze | Uwaga |
| --- | --- | --- |
| Panel ustawien i REST API | tak | port 21337 |
| WebSocket ze stanem na zywo | tak | |
| Testy, lint, sprawdzanie copy | tak | profil `test` |
| Front z hot reloadem | tak | profil `dev`, port 5173 |
| Wykrywanie bohatera | tak, jesli gra chodzi na hoscie | przez `host.docker.internal` |
| Nasluch mikrofonu | nie | kontener nie ma urzadzenia audio |
| Wciskanie klawiszy w grze | nie | kontener nie ma dostepu do klawiatury Windowsa |
| Ikona w zasobniku | nie | brak srodowiska graficznego |

Do grania nadal uruchamiasz `python main.py` albo zainstalowana aplikacje. Docker jest dla wygody przy pracy nad kodem i do CI.

## Uruchomienie

```
docker compose up panel
```

Panel: `http://127.0.0.1:21337/?token=dev-token`. Token ustawiasz przez `LOLVOICE_TOKEN`, domyslnie jest staly, zeby link nie zmienial sie po restarcie.

Front z hot reloadem, obok panelu:

```
docker compose --profile dev up
```

Vite stoi na `http://127.0.0.1:5173`, a zapytania `/api` i `/ws` przekazuje do kontenera `panel`.

Testy i lint:

```
docker compose --profile test run --rm tests
docker compose --profile test run --rm lint
docker compose --profile test run --rm tests python -m pytest -q tests/test_mappings.py
```

Obraz `dev` ma ffmpeg i espeak-ng, wiec testy audio z zestawu smoke tez sie uruchomia. Rozpoznawanie mowy pominie sie, dopoki nie zamontujesz katalogu z modelem:

```
docker compose --profile test run --rm -v %LOCALAPPDATA%\LoLVoice\models:/data/models tests python -m pytest -q -m audio
```

## Dane

Konfiguracja, logi, cache i modele siedza w wolumenie `lolvoice-data` podpietym pod `/data`, bo `LOLVOICE_HOME` wskazuje na ten katalog. Wolumen przezywa restart kontenera. Kasowanie:

```
docker compose down -v
```

Jesli chcesz uzywac danych z Windowsa zamiast wolumenu, podmien montowanie w `docker-compose.yml` na sciezke hosta.

## Dlaczego serwer przyjmuje polaczenia spoza loopbacka

Aplikacja domyslnie odpowiada tylko na `127.0.0.1`. W Dockerze przegladarka puka przez brame sieci kontenera, wiec jej adres to na przyklad `172.17.0.1` i zwykly filtr by ja odrzucil. Compose ustawia `LOLVOICE_TRUSTED_HOSTS` na zakresy sieci Dockera i tylko one dochodza dodatkowo. Poza Dockerem nie ustawiaj tej zmiennej.

Token jest wymagany zawsze, niezaleznie od tej zmiennej. Port jest zmapowany na `127.0.0.1:21337`, wiec nic nie wystawia sie do sieci lokalnej.

## Budowanie obrazow

```
docker compose build            # panel
docker compose --profile test build
```

Dockerfile ma trzy cele: `webui` buduje front w Node, `runtime` to lekki obraz z panelem i API, `dev` dokłada ffmpeg, espeak-ng i zaleznosci testowe. Obraz `runtime` instaluje tylko `requirements-docker.txt`, czyli bez sounddevice, pynput, pystray i whispera, bo kontener i tak nie ma z nich pozytku.
