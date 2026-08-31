"""Data Dragon: dane bohaterow, nazwy umiejetnosci, mapowania glosowe.

Zrodla danych, w kolejnosci:
1. katalog fixture (fixture_dir albo LOLVOICE_DDRAGON_FIXTURES), uzywany w testach,
2. cache na dysku w app.paths.CACHE_DIR,
3. Data Dragon (base_url),
4. mirror na GitHubie, gdy Data Dragon nie odpowiada.
"""

from __future__ import annotations

import difflib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from app import paths
from app.logging_setup import get_logger

log = get_logger("ddragon")

DDRAGON_BASE = "https://ddragon.leagueoflegends.com"
MIRROR_CHAMPION_URL = (
    "https://raw.githubusercontent.com/InFinity54/LoL_DDragon/master/latest/data/{lang}/championFull.json"
)
FALLBACK_VERSION = "14.1.1"


class LoLDataManager:
    def __init__(
        self,
        language: str = "pl_PL",
        base_url: str = DDRAGON_BASE,
        fixture_dir: str | Path | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.language = language
        self.base_url = base_url.rstrip("/")
        env_fixtures = os.environ.get("LOLVOICE_DDRAGON_FIXTURES")
        self.fixture_dir = Path(fixture_dir) if fixture_dir else (Path(env_fixtures) if env_fixtures else None)
        self.cache_dir = Path(cache_dir) if cache_dir else paths.CACHE_DIR
        self.version_dir = self.cache_dir / self.language
        self.latest_version: str | None = None
        self.champions_data: dict = {}
        self.items_data: dict = {}
        self.cache_metadata: dict = {}
        self.metadata_file = self.cache_dir / "metadata.json"

        self.version_dir.mkdir(parents=True, exist_ok=True)
        self._load_cache_metadata()

    # --- cache --------------------------------------------------------

    def _load_cache_metadata(self) -> None:
        try:
            if self.metadata_file.is_file():
                self.cache_metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.cache_metadata = {}

    def _save_cache_metadata(self) -> None:
        try:
            self.metadata_file.write_text(
                json.dumps(self.cache_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            log.debug("Could not write cache metadata: %s", exc)

    def _is_cache_outdated(self, cache_key: str, max_age_hours: int = 24) -> bool:
        entry = self.cache_metadata.get(cache_key)
        if not entry:
            return True
        try:
            last_update = datetime.fromisoformat(entry["last_update"])
        except (KeyError, TypeError, ValueError):
            return True
        return datetime.now() - last_update > timedelta(hours=max_age_hours)

    def _update_cache_metadata(self, cache_key: str, version: str) -> None:
        self.cache_metadata[cache_key] = {
            "version": version,
            "last_update": datetime.now().isoformat(),
        }
        self._save_cache_metadata()

    # --- zrodlo danych ------------------------------------------------

    def _fixture_file(self, name: str) -> Path | None:
        """Sciezka do pliku fixture, jesli katalog fixture jest ustawiony."""
        if not self.fixture_dir:
            return None
        stem, suffix = name.rsplit(".", 1)
        for candidate in (
            self.fixture_dir / f"{stem}.{self.language}.{suffix}",
            self.fixture_dir / self.language / name,
            self.fixture_dir / name,
        ):
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _unwrap(payload: dict) -> dict:
        """Data Dragon pakuje wszystko w koperte z kluczem 'data'."""
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload

    def get_latest_version(self) -> str:
        if not self.latest_version:
            try:
                import requests

                response = requests.get(f"{self.base_url}/api/versions.json", timeout=10)
                response.raise_for_status()
                self.latest_version = response.json()[0]
            except Exception as exc:  # brak sieci to normalny stan
                log.debug("Version lookup failed (%s), using %s", exc, FALLBACK_VERSION)
                self.latest_version = FALLBACK_VERSION
        return self.latest_version

    def _fetch_json(self, url: str, timeout: int = 30) -> dict:
        import requests

        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def fetch_champion_data(self, force_update: bool = False) -> dict:
        """Dane wszystkich bohaterow, fixture lub cache lub siec."""
        fixture = self._fixture_file("championFull.json")
        if fixture is not None:
            self.champions_data = self._unwrap(json.loads(fixture.read_text(encoding="utf-8")))
            log.debug("Loaded %d champions from fixture %s", len(self.champions_data), fixture)
            return self.champions_data

        data_path = self.version_dir / "championFull.json"
        cache_key = f"champions_{self.language}"

        if data_path.is_file() and not force_update and not self._is_cache_outdated(cache_key):
            try:
                self.champions_data = self._unwrap(json.loads(data_path.read_text(encoding="utf-8")))
                log.debug("Loaded %d champions from cache", len(self.champions_data))
                return self.champions_data
            except (OSError, json.JSONDecodeError):
                log.debug("Champion cache unreadable, refetching")

        version = self.get_latest_version()
        urls = [
            f"{self.base_url}/cdn/{version}/data/{self.language}/championFull.json",
            MIRROR_CHAMPION_URL.format(lang=self.language),
        ]
        for url in urls:
            try:
                data = self._unwrap(self._fetch_json(url))
                if not data:
                    continue
                try:
                    data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except OSError as exc:
                    log.debug("Could not cache champion data: %s", exc)
                self.champions_data = data
                self._update_cache_metadata(cache_key, version)
                log.info("Fetched %d champions from %s", len(data), url)
                return self.champions_data
            except Exception as exc:  # probujemy kolejne zrodlo
                log.warning("Champion data source failed (%s): %s", url, exc)

        # Ostatnia deska ratunku: przeterminowany cache jest lepszy niz nic.
        if data_path.is_file():
            try:
                self.champions_data = self._unwrap(json.loads(data_path.read_text(encoding="utf-8")))
                log.warning("Using stale champion cache, all sources unreachable")
                return self.champions_data
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    # --- umiejetnosci -------------------------------------------------

    def resolve_champion_key(self, champion_name: str) -> str | None:
        """Zamienia nazwe widoczna w grze na klucz Data Dragona.

        Live Client zwraca nazwe wyswietlana ("Wukong", "Kha'Zix", "Dr. Mundo"),
        a Data Dragon kluczuje bohaterow po id ("MonkeyKing", "Khazix", "DrMundo").
        Bez tego 21 bohaterow zostawalo bez mapowan, gdy endpoint umiejetnosci milczal.
        """
        if not champion_name:
            return None
        if not self.champions_data:
            self.fetch_champion_data()

        if champion_name in self.champions_data:
            return champion_name

        def squash(value: str) -> str:
            return re.sub(r"[^a-z0-9]", "", value.lower())

        wanted = squash(champion_name)
        for key, data in self.champions_data.items():
            if squash(key) == wanted or squash(str(data.get("name", ""))) == wanted:
                return key

        # "Nunu & Willump" kontra klucz "Nunu": dopuszczamy prefiks, ale dopiero
        # od czterech znakow, zeby krotkie nazwy nie zlepialy sie przypadkiem.
        for key, data in self.champions_data.items():
            for candidate in (squash(key), squash(str(data.get("name", "")))):
                if len(candidate) >= 4 and (wanted.startswith(candidate) or candidate.startswith(wanted)):
                    return key
        return None

    def get_champion_abilities(self, champion_name: str) -> dict:
        """Nazwy pasywki i Q, W, E, R danego bohatera."""
        if not self.champions_data:
            self.fetch_champion_data()

        resolved = self.resolve_champion_key(champion_name)
        champion_data = self.champions_data.get(resolved) if resolved else None
        if not champion_data:
            return {}

        spells = champion_data.get("spells") or []
        if len(spells) < 4:
            return {}

        return {
            "passive": champion_data.get("passive", {}).get("name", ""),
            "Q": spells[0]["name"],
            "W": spells[1]["name"],
            "E": spells[2]["name"],
            "R": spells[3]["name"],
        }

    def get_champion_sub_abilities(self, champion_name: str) -> dict[str, list[str]]:
        """Nazwy podumiejetnosci wyciagniete ze znacznikow spellName w leveltip."""
        if not self.champions_data:
            self.fetch_champion_data()

        resolved = self.resolve_champion_key(champion_name)
        champion_data = self.champions_data.get(resolved) if resolved else None
        if not champion_data:
            return {}

        sub_abilities: dict[str, list[str]] = {}

        for i, spell in enumerate(champion_data.get("spells", [])[:4]):
            key = ["Q", "W", "E", "R"][i]
            sub_abilities[key] = []

            if "leveltip" in spell and "label" in (spell["leveltip"] or {}):
                for label in spell["leveltip"]["label"]:
                    if "<spellName>" in label and "</spellName>" in label:
                        start = label.find("<spellName>") + len("<spellName>")
                        end = label.find("</spellName>")
                        if start < end:
                            sub_ability_name = label[start:end].strip()
                            if sub_ability_name and sub_ability_name not in sub_abilities[key]:
                                sub_abilities[key].append(sub_ability_name)

        return sub_abilities

    def get_hwei_sub_ability_mappings(self) -> dict[str, str]:
        """Hwei ma dwustopniowe czary, wiec dostaje wlasne mapowanie."""
        hwei_sub_mappings: dict[str, str] = {}

        sub_abilities = self.get_champion_sub_abilities("Hwei")
        if not sub_abilities:
            return {}

        key_order = ["q", "w", "e"]

        for theme_key, abilities in sub_abilities.items():
            if theme_key in ("Q", "W", "E") and abilities:
                for i, ability in enumerate(abilities):
                    if i < len(key_order):
                        hwei_sub_mappings[ability.lower()] = key_order[i]

        hwei_sub_mappings.update(
            {
                "spirala rozpaczy": "r",
                "czyszczenie pędzla": "r",
                "clear brush": "r",
                "brush clear": "r",
            }
        )

        return hwei_sub_mappings

    def create_voice_mappings(self, champion_name: str, keybinds: dict | None = None) -> dict[str, str]:
        """Mapowania fraza -> klawisz dla bohatera, na podstawie Data Dragon."""
        if keybinds is None:
            keybinds = {"Q": "q", "W": "w", "E": "e", "R": "r"}

        abilities = self.get_champion_abilities(champion_name)
        if not abilities:
            return {}

        mappings: dict[str, str] = {}
        sub_abilities = self.get_champion_sub_abilities(champion_name)

        for ability_key, ability_name in abilities.items():
            if ability_key == "passive" or not ability_name:
                continue

            key_binding = keybinds.get(ability_key, ability_key.lower())
            mappings[ability_name.lower()] = key_binding

            for variation in self._generate_ability_variations(ability_name):
                mappings.setdefault(variation, key_binding)

            if sub_abilities.get(ability_key):
                hwei_mappings = (
                    self.get_hwei_sub_ability_mappings() if champion_name.lower() == "hwei" else {}
                )
                for sub_ability in sub_abilities[ability_key]:
                    sub_key = hwei_mappings.get(sub_ability.lower(), key_binding)
                    mappings[sub_ability.lower()] = sub_key
                    for variation in self._generate_ability_variations(sub_ability):
                        mappings.setdefault(variation, sub_key)

        return mappings

    def _generate_ability_variations(self, ability_name: str) -> list[str]:
        """Warianty nazwy: bez znakow diakrytycznych, pojedyncze slowa, podfrazy."""
        variations: list[str] = []
        name_lower = ability_name.lower()

        diacritic_map = {
            "ą": "a", "ć": "c", "ę": "e", "ł": "l",
            "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        }

        normalized_name = name_lower
        for old, new in diacritic_map.items():
            normalized_name = normalized_name.replace(old, new)

        variations.append(normalized_name)

        words = normalized_name.split()

        if len(words) > 1:
            for word in words:
                if len(word) >= 4:
                    variations.append(word)

            for i in range(len(words)):
                for j in range(i + 1, len(words) + 1):
                    phrase = " ".join(words[i:j])
                    if len(phrase) >= 4:
                        variations.append(phrase)

        unique_variations: list[str] = []
        for var in variations:
            if var not in unique_variations:
                unique_variations.append(var)

        return unique_variations

    def get_ability_priority_score(self, ability_name: str) -> float:
        base_score = len(ability_name)
        word_count = len(ability_name.split())
        if word_count > 1:
            base_score += word_count * 2
        return float(base_score)

    def find_similar_abilities(self, champion_name: str, threshold: float = 0.6) -> list[tuple[str, str, float]]:
        """Pary umiejetnosci, ktore brzmia podobnie i moga sie mylic."""
        abilities = self.get_champion_abilities(champion_name)
        if not abilities:
            return []

        similar_pairs = []
        ability_list = [(k, v) for k, v in abilities.items() if k != "passive"]

        for i, (_key1, name1) in enumerate(ability_list):
            for _key2, name2 in ability_list[i + 1:]:
                similarity = difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
                if similarity >= threshold:
                    similar_pairs.append((name1, name2, similarity))

        return similar_pairs

    def suggest_recognition_accuracy(self, champion_name: str) -> float:
        """Sugerowany prog dopasowania dla bohatera."""
        similar_abilities = self.find_similar_abilities(champion_name, threshold=0.4)

        if not similar_abilities:
            return 0.5

        max_similarity = max(pair[2] for pair in similar_abilities)

        if max_similarity > 0.8:
            return 0.85
        if max_similarity > 0.6:
            return 0.75
        return 0.70

    def get_all_champions(self) -> list[str]:
        if not self.champions_data:
            self.fetch_champion_data()
        return list(self.champions_data.keys())

    # --- przedmioty ---------------------------------------------------

    def fetch_items_data(self, force_update: bool = False) -> dict:
        fixture = self._fixture_file("item.json")
        if fixture is not None:
            self.items_data = self._unwrap(json.loads(fixture.read_text(encoding="utf-8")))
            return self.items_data

        version = self.get_latest_version()
        data_path = self.version_dir / "item.json"
        cache_key = f"items_{self.language}"

        if data_path.is_file() and not force_update and not self._is_cache_outdated(cache_key):
            try:
                return self._unwrap(json.loads(data_path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                pass

        try:
            url = f"{self.base_url}/cdn/{version}/data/{self.language}/item.json"
            data = self._unwrap(self._fetch_json(url))
            try:
                data_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
            self._update_cache_metadata(cache_key, version)
            log.info("Fetched %d items", len(data))
            return data
        except Exception as exc:  # brak sieci nie moze wywrocic aplikacji
            log.warning("Error fetching items data: %s", exc)
            return {}

    def search_items(self, query: str) -> list[tuple[str, str, float]]:
        """Piec najlepszych trafien w nazwach przedmiotow z Summoner's Rift."""
        items_data = self.fetch_items_data()
        if not items_data:
            return []

        matches = []
        query_lower = query.lower()

        for item_id, item_data in items_data.items():
            item_name = item_data.get("name", "")
            if not item_name:
                continue

            if not item_data.get("maps", {}).get("11", False):
                continue

            if query_lower == item_name.lower():
                matches.append((item_name, item_id, 1.0))
                continue

            if item_name.lower().startswith(query_lower):
                matches.append((item_name, item_id, 0.9))
                continue

            if query_lower in item_name.lower():
                matches.append((item_name, item_id, 0.8))
                continue

            similarity = difflib.SequenceMatcher(None, query_lower, item_name.lower()).ratio()
            if similarity >= 0.6:
                matches.append((item_name, item_id, similarity))

        matches.sort(key=lambda x: x[2], reverse=True)
        return matches[:5]

    # --- jezyk --------------------------------------------------------

    def get_supported_languages(self) -> list[str]:
        return [
            "en_US", "pl_PL", "de_DE", "es_ES", "fr_FR", "it_IT",
            "pt_BR", "ru_RU", "ko_KR", "zh_CN", "zh_TW", "ja_JP",
            "tr_TR", "th_TH", "vi_VN", "id_ID", "ar_AE", "cs_CZ",
            "el_GR", "hu_HU", "ro_RO",
        ]

    def change_language(self, new_language: str) -> bool:
        if new_language in self.get_supported_languages():
            self.language = new_language
            self.version_dir = self.cache_dir / self.language
            self.version_dir.mkdir(parents=True, exist_ok=True)
            self.champions_data = {}
            self.items_data = {}
            return True
        return False

    def auto_update_data(self) -> bool:
        """Odswieza dane, jesli cache ma wiecej niz szesc godzin."""
        try:
            cache_key = f"champions_{self.language}"
            if self._is_cache_outdated(cache_key, max_age_hours=6):
                log.info("Champion data outdated, updating")
                self.fetch_champion_data(force_update=True)
                return True
            log.debug("Champion data up to date")
            return False
        except Exception as exc:  # aktualizacja jest opcjonalna
            log.warning("Auto update failed: %s", exc)
            return False
