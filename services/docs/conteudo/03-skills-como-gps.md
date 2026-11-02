# 3. Skills como GPS

!!! abstract "Resumo executivo"
    Pelo gateway, o agente enxerga 41 tools de 8 sistemas. Sem orientação, ele precisa adivinhar quais usar e em que ordem, e é aí que gasta mais, erra mais e quebra regras.

    A **skill** é o GPS: um roteiro escrito pelo banco que diz quais tools usar, em que ordem, o que conferir entre uma e outra e o que fazer quando o caminho muda.

    Ela é a **porta de entrada** para a camada de contexto. O agente começa perguntando "quais roteiros existem?", e não "o que eu consigo chamar?". Com uma skill ativa, o gateway só deixa passar o que o roteiro permite: tentar outra coisa é **contramão**.

## Aprofundamento técnico

### O que é uma Agent Skill

Uma skill é uma pasta com um `SKILL.md`: frontmatter YAML (nome, descrição e metadados) e instruções em markdown. Ao lado dele ficam arquivos de apoio, que o agente lê só quando precisa. A skill principal da demo:

```yaml
--8<-- "contratacao-seguro-residencial/SKILL.md:1:12"
```

- `allowed-tools` é o campo padrão do formato Agent Skills: a lista das tools que a skill usa.
- Em `metadata` ficam os dados de governança do Banco Bússola:
  - as skills reutilizadas (`usa-skills`);
  - a alçada;
  - quando a aprovação humana é obrigatória.

As quatro skills da demo:

| Skill | Papel |
| --- | --- |
| `contratacao-seguro-residencial` | Rota principal: as 9 paradas, do pedido à apólice |
| `verificacao-consentimento` | Trecho reutilizável: base legal LGPD e renovação |
| `cotacao-multisseguradora` | Rota econômica: cotar as três e comparar |
| `escalonamento-humano` | O pedágio: aprovação de um especialista acima da alçada |

### SEP-2640: skills servidas por MCP

A extensão oficial `io.modelcontextprotocol/skills` serve skills pelo primitivo *resources*. O SDK MCP em Python ainda não traz essa extensão pronta, então ela foi implementada no `skills-mcp` sobre o mecanismo genérico de extensões do SDK (SEP-2133). O fluxo, como o Raio-X vai mostrar:

```
1. skills/list            → nomes, descrições e arquivos de cada skill, com digest SHA-256
2. resources/read         skill://contratacao-seguro-residencial/SKILL.md
                          (o host confere tamanho, digest e frontmatter antes de usar)
3. tools/call             cliente.obter_perfil ...       _meta: {"bussola/skill": "skill://…/SKILL.md"}
4. resources/read         skill://…/references/elegibilidade.md   (só ao chegar na parada 4)
```

A resposta de `skills/list` traz, para cada skill:

```json
{
  "uri": "skill://verificacao-consentimento/SKILL.md",
  "frontmatter": { "name": "verificacao-consentimento", "description": "…", "allowed-tools": "…" },
  "resources": [
    { "uri": "skill://verificacao-consentimento/SKILL.md", "digest": "sha256:40cc…", "size": 1690 }
  ]
}
```

O digest garante que o que o agente lê é o que foi listado. O gateway repassa as entradas sem tocá-las, então a verificação vale de ponta a ponta. O módulo `bussola_comum.skills` concentra o consumo da extensão: listar, obter e ler com verificação. Se o suporte nos SDKs mudar, só ele muda.

### Progressive disclosure: o zoom do mapa

O `SKILL.md` principal não carrega tudo. Cada trecho tem seu arquivo, lido só quando o agente chega lá:

- `references/elegibilidade.md`: parada 4;
- `references/cotacao.md`: parada 6;
- `references/emissao.md`: parada 9;
- `references/desvios.md`: a regra de recálculo para cada incidente.

No mapa, é o zoom no bairro do trecho em execução. No custo, são menos tokens no contexto.

### Governança no gateway: a contramão

O agente declara a skill ativa em cada chamada, no `_meta` (`"bussola/skill": "skill://contratacao-seguro-residencial/SKILL.md"`). O gateway então:

1. **barra tools desligadas pelo apresentador** (`motivo: desligada`);
2. **barra skill desconhecida** (`motivo: skill_desconhecida`);
3. **só deixa passar** as tools de `allowed-tools`, somadas às das skills de `usa-skills`. O resto é **contramão** (`motivo: fora_da_skill`), recusada sem chegar ao servidor e com a lista do que é permitido.

Nenhuma das 15 tools de distração está em skill alguma, nem os três atalhos legados (veja abaixo). **Sem skill declarada, o gateway não restringe nada**: é assim que as cenas 2 e 3 mostram o agente sem GPS.

O código do gateway que decide, a cada chamada, se a tool passa. É o trecho real, citado do repositório:

```python
--8<-- "gateway/servidor_mcp.py:governanca"
```

### A ordem também é lei

Uma skill é um workflow, e workflow tem ordem. Até aqui o gateway sabia *quais* tools a skill permite, mas não *quando*. Agora a skill declara, num `workflow.yaml`, o que precisa ter acontecido antes de cada tool:

```yaml
--8<-- "contratacao-seguro-residencial/workflow.yaml"
```

O mesmo arquivo, desenhado. Cada seta é "precisa ter acontecido antes"; as vermelhas, "impede". O diagrama é gerado no build a partir do `workflow.yaml`.

![A ordem da skill de contratação](assets/diagramas/skill-contratacao-seguro-residencial.svg)

Com essa skill ativa, o gateway:

1. **exige a execução** em `_meta["bussola/execucao"]`, porque a ordem só existe dentro de uma execução (`motivo: execucao_nao_identificada`);
2. **guarda os fatos da execução:** cada tool que deu certo, com o resultado, em `bussola:fatos:<execução>`;
3. **barra a tool fora de ordem** (`motivo: fora_de_ordem`) e diz o que falta: *"Contramão: seguradoras.cotar_seguro exige antes: risco.consultar_elegibilidade; consentimento.verificar com finalidade = finalidade-compartilhamento-seguradoras, permitido = true."*

Um pré-requisito pode olhar o resultado. Ler o imóvel exige um `consentimento.verificar` que **deu** `permitido: true` para a finalidade de oferta; não basta ter chamado. E impedimentos fecham portas: depois de agendar uma vistoria, pagar e emitir ficam bloqueados.

Os pré-requisitos são **de negócio, não uma fila rígida**. O agente ainda pode cotar antes de avaliar a adequação, porque isso não fere nenhuma regra. O que ele não pode é gerar a proposta sem a adequação.

### Atalhos legados: o perigo de quem não tem GPS

Bancos reais têm atalhos que parecem certos para a tarefa, mas pulam regras. A demo tem três:

| Tool | O que promete | O que pula |
| --- | --- | --- |
| `seguradoras.contratacao_expressa` | Cota, aceita, debita e emite numa chamada | Consentimento, adequação, alçada, vistoria e o sim da cliente |
| `cliente.obter_dossie_completo` | Tudo sobre a cliente numa chamada | Minimização de dados (LGPD) |
| `seguradoras.cotar_seguro_v1` | Cotação mais rápida | Proveniência e laudo |

Eles funcionam: a contratação expressa emite uma apólice de verdade (`EXP-…`). Com skill, o gateway os barra (`fora_da_skill`). Sem skill, nada os impede. É a diferença entre bom comportamento e garantia.

Cada chamada registra a skill na proveniência e no evento `tool.called`. As leituras do protocolo também viram eventos: `skills.listed` e `resource.read`.
