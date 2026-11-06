# O grafo de contexto

!!! abstract "Resumo"
    A camada de contexto é um grafo de propriedades no Neo4j, montado de uma ontologia versionada em YAML: o **esquema (T-Box)** diz que tipos e relações existem, e as **instâncias (A-Box)** são o banco de verdade. Sobre elas há duas camadas: o **estado vivo**, que o simulador muda em tempo real, e a **proveniência**, que diz de onde veio cada nó e cada relação. O agente nunca escreve Cypher: ele chama 6 tools do `contexto-mcp`, e cada uma faz uma consulta fixa e parametrizada.

## As camadas e a profundidade

Os números abaixo são calculados no build, a partir da ontologia, pelo mesmo carregador que o `seed` usa.

![As quatro camadas do grafo: esquema, instâncias, estado vivo e proveniência](../assets/diagramas/camadas.svg)

--8<-- "numeros-grafo.md"

**Os caminhos mais longos do grafo de instâncias** mostram até onde o contexto vai: de uma jornada até a norma que rege uma alçada.

--8<-- "caminhos.md"

## O modelo (T-Box), em diagrama de classes

**Como ler o diagrama:**

- **Cada caixa é um tipo de entidade,** agrupado pelo bairro do mapa, na mesma cor.
- **Dentro da caixa:**
  - os rótulos que o tipo recebe no Neo4j (`:Entidade:<Tipo>`) e quantas instâncias ele tem;
  - as **propriedades observadas** nas instâncias (`attr_*`);
  - a marca **+ estado vivo** nos tipos que o simulador muda.
- **As propriedades que toda entidade tem** (id, nomes, bairro, posição no mapa e proveniência) aparecem uma vez só, na caixa "Toda entidade".
- **Cada seta é uma relação,** com a **multiplicidade observada** nas pontas. Por exemplo, `Cliente 1 → 1..n Conta` quer dizer que toda cliente tem uma ou mais contas, e que cada conta é de uma cliente. O esquema declara origem e destino, mas não cardinalidade. Por isso a multiplicidade é **observada** nas instâncias, e não imposta.

![T-Box: os tipos de entidade do domínio, por bairro, com propriedades e relações](../assets/diagramas/tbox.svg)

**A jornada,** com Jornada, Rota e Parada, toca quase todos os tipos. Por isso ela tem um diagrama próprio. Cada parada **toca** os sistemas e entidades que usa, **exige** regras e **está sujeita** a alçadas e políticas. É daí que a tool `contexto.consultar_rota` tira o que cada parada vai precisar.

![T-Box da jornada: Jornada, Rota e Parada e os tipos que cada parada toca](../assets/diagramas/tbox-jornada.svg)

### Os tipos

--8<-- "tipos.md"

### As relações

A tabela mostra a origem e o destino **permitidos** pelo esquema e, ao lado, o que aparece de fato nas instâncias: a multiplicidade e o número de arestas.

--8<-- "relacoes.md"

## As instâncias (A-Box): a Ana

**O subgrafo da Ana, a até 2 saltos:**

- as contas, o imóvel e os produtos dela;
- os consentimentos e as finalidades que eles autorizam;
- os scores e as regras que os usam.

Cada nó traz o tipo, o id e a **fonte** de onde veio. Se a confiança não for alta, ela aparece em laranja.

![A-Box: a Ana e tudo o que está a até dois saltos dela no grafo](../assets/diagramas/abox-ana.svg)

## O modelo físico no Neo4j

- **Um nó por entidade,** com dois rótulos: `:Entidade` e o do tipo (`:Cliente`, `:Imovel`…).
- **Uma constraint de unicidade** em `Entidade.id`: as consultas sempre partem de um id.
- **As propriedades ficam achatadas,** porque o Neo4j não guarda mapas aninhados:
  - os atributos do domínio levam o prefixo `attr_`;
  - a proveniência leva o prefixo `prov_` (`prov_fonte`, `prov_data`, `prov_responsavel` e `prov_confianca`) e vale **também em cada relação**;
  - o estado vivo (`status`, `latencia_ms`, `custo_estimado`, `vigencia_*`) fica no nível de cima, para o simulador mudar com um `SET n += …`.
- **Os tipos de relação vêm do esquema validado,** nunca de entrada externa. Por isso o `seed` pode interpolá-los no Cypher com segurança.

**A carga:** o `seed` apaga tudo, valida a ontologia e o layout do mapa e escreve os nós e as relações em lote (`UNWIND`), agrupados por tipo:

```python
--8<-- "contexto/seed.py:carga"
```

## As consultas de cada tool

O agente nunca escreve Cypher. Cada tool do `contexto-mcp` faz **uma consulta fixa e parametrizada**, citada abaixo do próprio código. A profundidade que cada uma alcança está no padrão do `MATCH`.

=== "consultar_regras"

    As regras que valem para uma entidade, a **até 2 saltos** por `EXIGE`, `REQUER`, `SUJEITA_A` e `REGIDO_POR`, com o caminho mais curto até cada uma. É o que responde "o que preciso cumprir aqui?".

    ```python
    --8<-- "contexto/grafo.py:regras"
    ```

=== "consultar_rota"

    As rotas de uma jornada, cada parada na ordem (`PASSA_POR`) e o que cada parada usa ou toca (`USA` e `TOCA`). São 3 saltos: Jornada → Rota → Parada → sistema ou regra.

    ```python
    --8<-- "contexto/grafo.py:rotas"
    ```

=== "consultar_entidade"

    Uma entidade e todas as relações dela, nos dois sentidos, com a proveniência de cada relação. É **1 salto**.

    ```python
    --8<-- "contexto/grafo.py:entidade"
    ```

=== "consultar_proveniencia"

    De onde veio um dado. Com `relacionado_a`, diz também de onde veio a relação entre as duas entidades.

    ```python
    --8<-- "contexto/grafo.py:proveniencia"
    ```

=== "consultar_estado"

    O estado vivo, o trânsito: quem está fora do ar, degradado ou com a vigência vencida.

    ```python
    --8<-- "contexto/grafo.py:estado"
    ```

=== "buscar_entidades"

    A busca por texto, tipo ou bairro, para o agente achar o id de onde partir.

    ```python
    --8<-- "contexto/grafo.py:buscar"
    ```

**O estado vivo, do lado do simulador:** os incidentes mudam o grafo pela rota interna do `contexto-mcp`, que só o simulador conhece (`SIMULADOR_TOKEN`). Eles não passam pelo gateway nem pelo agente.

```python
--8<-- "contexto/grafo.py:efeitos"
```

## Fontes no repositório

| O quê | Onde |
| --- | --- |
| Esquema (tipos e relações) | `services/contexto-mcp/ontologia/esquema.yaml` |
| Instâncias, com a proveniência | `services/contexto-mcp/ontologia/instancias/*.yaml` |
| Bairros e cidade | `services/contexto-mcp/ontologia/bairros.yaml` |
| Carregador e validação | `services/contexto-mcp/src/contexto_mcp/ontologia.py` |
| Carga no Neo4j | `services/contexto-mcp/src/contexto_mcp/seed.py` |
| Consultas | `services/contexto-mcp/src/contexto_mcp/grafo.py` |
| Gerador destas tabelas | `services/docs/gerar/referencia.py` |
