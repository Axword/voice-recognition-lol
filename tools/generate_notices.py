"""Buduje THIRD-PARTY-NOTICES.md z metadanych faktycznie zainstalowanych pakietow."""
import re
from importlib.metadata import distributions
from pathlib import Path

RUNTIME = [
    line.split("#")[0].strip()
    for line in Path("requirements.txt").read_text(encoding="utf-8").splitlines()
]
names = set()
for entry in RUNTIME:
    if not entry:
        continue
    m = re.match(r"^([A-Za-z0-9._-]+)", entry)
    if m:
        names.add(m.group(1).lower().replace("_", "-"))

# Kilka pakietow nie podaje licencji w metadanych w czytelnej formie.
FALLBACK = {
    "numpy": "BSD-3-Clause",
    "pywin32": "PSF-2.0",
    "colorama": "BSD-3-Clause",
}

rows = {}
for d in distributions():
    name = (d.metadata.get("Name") or "").lower().replace("_", "-")
    if name not in names:
        continue
    lic = d.metadata.get("License-Expression") or d.metadata.get("License") or ""
    if not lic or len(lic) > 40 or "\n" in lic:
        cls = [c for c in d.metadata.get_all("Classifier") or [] if c.startswith("License")]
        lic = cls[0].split("::")[-1].strip() if cls else ""
    if not lic or lic.endswith("License") or lic == "":
        lic = FALLBACK.get(name, lic or "patrz pakiet")
    url = ""
    for key in ("Home-page", "Project-URL"):
        vals = d.metadata.get_all(key) or []
        for v in vals:
            if "http" in v:
                url = v.split(",")[-1].strip()
                break
        if url:
            break
    rows[d.metadata["Name"]] = (lic.strip(), url)

lines = [
    "# Licencje zaleznosci",
    "",
    "LoL Voice Controller jest na GPL-3.0-or-later (plik LICENSE). Instalator i",
    "paczka portable zawieraja ponizsze biblioteki, kazda na wlasnej licencji.",
    "",
    "Dwie z nich, `pynput` i `pystray`, sa na LGPL-3.0. Licencja ta wymaga, aby",
    "uzytkownik mogl podmienic te biblioteki na wlasna wersje. Warunek jest",
    "spelniony: aplikacja jest wolnym oprogramowaniem, kod zrodlowy jest publiczny,",
    "a biblioteki leza jako osobne pliki w katalogu `_internal` obok programu.",
    "",
    "Zestawienie generuje `tools/generate_notices.py` z metadanych zainstalowanych",
    "pakietow, wiec odswieza sie razem z zaleznosciami.",
    "",
    "| Pakiet | Licencja | Strona |",
    "| --- | --- | --- |",
]
for name in sorted(rows, key=str.lower):
    lic, url = rows[name]
    lines.append(f"| {name} | {lic} | {url or ''} |")
lines.append("")

Path("THIRD-PARTY-NOTICES.md").write_text("\n".join(lines), encoding="utf-8")
print(f"zapisano {len(rows)} pakietow")
