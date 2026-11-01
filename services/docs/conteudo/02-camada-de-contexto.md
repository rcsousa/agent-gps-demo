# 2. A camada de contexto

!!! abstract "Resumo executivo"
    A camada de contexto é o **mapa do negócio** que o agente consulta antes de agir. Ela reúne quatro coisas:

    - **O mapa:** quem é a cliente, que produtos existem, quais regras valem e quem são os parceiros.
    - **O trânsito:** o que está no ar, lento ou fora agora.
    - **As regras de trânsito:** consentimento, alçadas e políticas.
    - **A origem de cada informação.**

    Sem esse mapa, o agente adivinha. Com ele, escolhe rotas, respeita regras e explica o que fez. Na demo, esse mapa é uma cidade com 6 bairros e cerca de 180 lugares, sempre igual em todo ensaio.

## Aprofundamento técnico

### A metáfora, peça por peça

| Navegação | Camada de contexto | Onde fica no código |
| --- | --- | --- |
| Bairros | Domínios do negócio | `ontologia/bairros.yaml` |
| Pontos de interesse | Entidades (cliente, produto, regra, API...) | `ontologia/instancias/*.yaml` |
| Ruas | Relações entre entidades | campo `relacoes` de cada arquivo, validado por `ontologia/esquema.yaml` |
| Trânsito | Estado vivo: `status`, `latencia_ms`, `custo_estimado`, `vigencia` | campo `estado` das entidades |
| Placas e origem | Proveniência: fonte, data, responsável e confiança | campo `proveniencia` de nós e relações |

Tudo isso é versionado em YAML, legível por gente. A cada `docker compose up`, o serviço `seed` apaga o Neo4j e recarrega esse estado-base. Assim, todo ensaio começa do mesmo ponto.

### Os bairros

As posições seguem o infográfico da demo. A plateia passa a reconhecer os lugares ("o bairro do Risco fica ali") ao longo da apresentação.

```yaml
--8<-- "bairros.yaml:bairros"
```

Dentro de cada bairro, os nós são distribuídos por layout de forças, com semente fixa, e encaixados numa grade de quadras. O resultado fica salvo em `ontologia/layout.json`, e um teste garante que ele corresponde à ontologia. Relações entre bairros viram **avenidas**.

### Tipos de entidade

```yaml
--8<-- "esquema.yaml:tipos"
```

### As ruas: relações permitidas

O esquema diz quais ruas existem e entre quais tipos de lugar. Uma relação fora do esquema faz o seed falhar com uma mensagem clara.

```yaml
--8<-- "esquema.yaml:relacoes"
```

### Estado vivo: o trânsito

As APIs das seguradoras têm status, latência e custo, e é daí que saem as estimativas de rota.

O trânsito muda de verdade. Quando o apresentador derruba a API de cotação da Âncora, o simulador grava `status: fora` nessa entidade, no grafo e nos sistemas ao mesmo tempo. Na pergunta seguinte, `consultar_rota` devolve a rota rápida **bloqueada**, com o alerta "trecho interditado", e a cotação da Âncora falha. Nada é roteirizado na tela: o mapa só reflete o estado.

```yaml
--8<-- "instancias/parceiros.yaml:apis"
```

### A proveniência governa a consequência

Todo nó e toda relação dizem de onde vieram. Quanto maior o impacto de uma decisão, mais forte precisa ser essa origem. A cliente Elisa existe para mostrar isso: o cadastro dela veio de uma planilha legada, com confiança **baixa**.

```yaml
--8<-- "instancias/cliente.yaml:elisa"
```

A pergunta `consultar_proveniencia` devolve a origem de qualquer elemento:

```json
{
  "alvo": { "id": "cliente-elisa", "nome": "Elisa Prado", "bairro": "cliente" },
  "proveniencia": {
    "fonte": "Planilha importada (cadastro legado)",
    "data": "2023-04-11",
    "responsavel": "Desconhecido",
    "confianca": "baixa"
  }
}
```

### Como o agente consulta o mapa

O agente nunca escreve Cypher. O `contexto-mcp` expõe perguntas de negócio como tools MCP, que chegam ao agente pelo gateway como `contexto.*`:

| Tool | Pergunta que responde |
| --- | --- |
| `buscar_entidades` | O que existe no mapa com este nome, tipo ou bairro? |
| `consultar_entidade` | O que sei sobre este lugar e o que está ligado a ele? |
| `consultar_regras` | Que regras, alçadas, normas e bases legais valem aqui? |
| `consultar_estado` | Como está o trânsito agora? |
| `consultar_proveniencia` | De onde veio esta informação, e com que confiança? |
| `consultar_rota` | Quais rotas levam ao destino, e quanto custa cada uma agora? |

O recurso MCP `contexto://mapa` entrega o mapa completo (bairros, rio, avenidas, nós com posição e estado) para o desenho da cidade. Ele não é tool, porque não faz sentido gastar tokens do modelo com ele.
