#!/usr/bin/env python3
"""Sprawdzenie zdrowia kontenera: czy API odpowiada i czy token dziala.

Kod wyjscia 0 oznacza zdrowy kontener, 1 kazdy inny przypadek. Uzywane przez
HEALTHCHECK w Dockerfile, ale dziala tez recznie:

    python tools/healthcheck.py --port 21337 --token dev-token
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request


def check(host: str, port: int, token: str, timeout: float) -> int:
    url = f"http://{host}:{port}/api/v1/status"
    request = urllib.request.Request(url, headers={"X-Auth-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - staly, lokalny adres
            if response.status != 200:
                print(f"unhealthy: HTTP {response.status}")
                return 1
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"unhealthy: HTTP {exc.code}, sprawdz LOLVOICE_TOKEN")
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"unhealthy: brak odpowiedzi ({exc})")
        return 1
    except json.JSONDecodeError:
        print("unhealthy: odpowiedz nie jest poprawnym JSON")
        return 1

    if "version" not in payload:
        print("unhealthy: odpowiedz bez pola version")
        return 1
    print(f"ok: wersja {payload['version']}, silnik {payload.get('engine_id')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Health check lokalnego API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("LOLVOICE_PORT", "21337")))
    parser.add_argument("--token", default=os.environ.get("LOLVOICE_TOKEN", ""))
    parser.add_argument("--timeout", type=float, default=4.0)
    args = parser.parse_args()
    return check(args.host, args.port, args.token, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
