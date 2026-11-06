# Skills, prompts e tools

!!! abstract "Resumo"
    O que o agente sabe fazer chega por três vias, todas pelo gateway:

    - **as tools**, as ações nos sistemas do banco;
    - **os prompts**, a persona de cada canal de atendimento;
    - **as skills**, os procedimentos do banco, com as tools permitidas e a ordem.

    A skill é a porta de entrada: o agente lista as skills, lê só a que serve ao pedido, e a partir daí o gateway passa a valer o que ela permite.

## Skills: o formato

Uma skill é uma pasta com um `SKILL.md` e arquivos de apoio.

- **O `SKILL.md`** abre com um cabeçalho de metadados (*frontmatter*): o nome, a descrição, as tools permitidas e os metadados de que o banco precisa, como as skills que ela usa, a alçada e a rota. O corpo, em Markdown, é o procedimento.

```yaml
--8<-- "contratacao-seguro-residencial/SKILL.md:1:12"
```

- **O `workflow.yaml`,** opcional, declara a ordem: o que precisa ter acontecido nesta execução antes de cada tool, e o que impede uma tool. Ele é **lido pelo gateway**, não pelo modelo: a ordem é imposta, não sugerida.

## Skills: o ciclo (SEP-2640)

As skills são servidas por MCP pela extensão `io.modelcontextprotocol/skills`. O agente as descobre e lê como qualquer cliente MCP leria:

1. **`skills/list`** devolve cada skill com o URI, o frontmatter e a lista de arquivos, com o tamanho e o **digest SHA-256** de cada um.
2. **`resources/read skill://<skill>/SKILL.md`** devolve o arquivo. O cliente confere o tamanho e o digest contra a lista. Se divergirem, o arquivo é recusado, e um intermediário não consegue trocar o procedimento no caminho.
3. **Os arquivos de apoio** (`references/*.md`) são lidos só quando a skill manda: é o *progressive disclosure*, descrito no capítulo 3.
4. Carregada a skill, o agente marca cada chamada com `_meta["bussola/skill"]`, e **o gateway passa a aplicar** as `allowed-tools` e o `workflow.yaml`.

O gateway repassa as entradas como vieram do `skills-mcp`, então os digests valem de ponta a ponta:

```python
--8<-- "gateway/servidor_mcp.py:skills"
```

## Prompts: as três camadas

O prompt de sistema do agente é montado em três camadas, cada uma com um dono:

| Camada | O que diz | De onde vem |
| --- | --- | --- |
| 1. Persona do canal | Quem é o agente e com quem fala (a cliente no app, o gerente na agência…) | **Do banco, pelo gateway:** o prompt MCP `canais.atendimento_<canal>`, servido pelo `canais-mcp` |
| 2. Regras do host | Como usar as ferramentas que só o agente tem (conversa, narração, leitura de skills) | Do código do agente (`services/agent/src/agent/prompts.py`) |
| 3. O workflow do negócio | O procedimento, as tools e a ordem | **Da skill**, que o modelo carrega quando precisa |

A persona e o procedimento são do banco, e mudam sem tocar no agente. O agente só traz o que é dele: como conversar e como narrar. O detalhe está no capítulo 6, em "O prompt do agente em três camadas".

## O catálogo completo

Tudo o que o gateway expõe hoje, gerado do catálogo versionado e conferido pelo smoke contra o gateway vivo.

- Os parâmetros com `?` são opcionais.
- A descrição de cada tool é a que o modelo lê.

--8<-- "catalogo.md"

## Fontes no repositório

| O quê | Onde |
| --- | --- |
| Skills | `services/skills-mcp/skills/<skill>/` (`SKILL.md`, `workflow.yaml`, `references/`) |
| Cliente da extensão de skills | `libs/bussola_comum/src/bussola_comum/skills.py` |
| Personas por canal | `services/canais-mcp/` |
| Prompt do agente | `services/agent/src/agent/prompts.py` |
| Catálogo | `services/smoke/referencia/catalogo.json` |
