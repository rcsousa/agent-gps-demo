"""Catálogo do que o gateway expõe ao agente: tools, prompts e skills, para a referência técnica.

O build do docs não tem o gateway no ar, por isso o catálogo é um arquivo versionado
(services/smoke/referencia/catalogo.json). O smoke confere que ele é igual ao gateway vivo:
mudou uma tool sem regenerar o catálogo, o teste falha.

Uso (pelo script): ./scripts/gerar-referencia.sh
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from bussola_comum.cliente_mcp import conectar
from bussola_comum.skills import listar_skills, tools_permitidas

GATEWAY = "http://mcp-gateway:8000/mcp"
ARQUIVO = Path(__file__).resolve().parents[2] / "referencia" / "catalogo.json"


async def montar() -> dict:
    async with conectar(GATEWAY, os.environ["GATEWAY_TOKEN"]) as cliente:
        tools = (await cliente.list_tools()).tools
        prompts = (await cliente.list_prompts()).prompts
        skills = await listar_skills(cliente)
    return {
        "tools": sorted(
            (
                {"nome": t.name, "descricao": t.description or "", "parametros": t.input_schema or {}}
                for t in tools
            ),
            key=lambda t: t["nome"],
        ),
        "prompts": sorted(
            (
                {
                    "nome": p.name,
                    "descricao": p.description or "",
                    "argumentos": [a.name for a in (p.arguments or [])],
                }
                for p in prompts
            ),
            key=lambda p: p["nome"],
        ),
        "skills": sorted(
            (
                {
                    "nome": s["frontmatter"]["name"],
                    "uri": s["uri"],
                    "descricao": s["frontmatter"].get("description", ""),
                    "tools_permitidas": sorted(tools_permitidas(s["frontmatter"])),
                    "arquivos": sorted(a["uri"] for a in s["resources"]),
                }
                for s in skills
            ),
            key=lambda s: s["nome"],
        ),
    }


def serializar(catalogo: dict) -> str:
    return json.dumps(catalogo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(serializar(asyncio.run(montar())), encoding="utf-8")
    print(f"Catálogo gravado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
