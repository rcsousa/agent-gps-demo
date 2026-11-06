"""O catálogo da referência técnica (versionado) é o que o gateway expõe de verdade."""

import asyncio
from pathlib import Path

from smoke.referencia import montar, serializar

ARQUIVO = Path(__file__).resolve().parents[1] / "referencia" / "catalogo.json"


def test_catalogo_versionado_igual_ao_gateway_vivo():
    vivo = serializar(asyncio.run(montar()))
    versionado = ARQUIVO.read_text(encoding="utf-8")
    assert versionado == vivo, (
        "O catálogo da referência técnica está desatualizado em relação ao gateway. "
        "Rode ./scripts/gerar-referencia.sh e versione services/smoke/referencia/catalogo.json."
    )
