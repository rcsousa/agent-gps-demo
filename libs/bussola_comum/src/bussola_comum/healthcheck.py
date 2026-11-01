"""Healthcheck do Docker: python -m bussola_comum.healthcheck <url>.

Sai com 0 se a URL responder 2xx, 1 caso contrário. Só usa a stdlib.
"""

import sys
import urllib.request


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/saude"
    try:
        with urllib.request.urlopen(url, timeout=3) as resposta:
            return 0 if 200 <= resposta.status < 300 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
