# Referência técnica

!!! abstract "Para quem é"
    Para arquitetos e engenheiros que querem o **como**, sem metáfora. Os capítulos dos bastidores explicam o porquê. Aqui estão os contratos, os modelos e o código que roda.

## Como esta seção é feita

**Nada aqui é escrito à mão se puder ficar desatualizado.** Tudo sai do repositório no build do site:

- **Diagramas:**
  - o grafo (T-Box e A-Box) é lido pelo mesmo carregador de ontologia que o `seed` usa para montar o Neo4j;
  - a arquitetura vem do `docker-compose.yml`, do `nginx.conf` e dos módulos de cada serviço;
  - o gateway vem do `upstreams.yaml`;
  - as sequências vêm de **execuções reais gravadas** (`gravacoes/*.jsonl`).
- **Números e tabelas:** são calculados no build e inseridos nas páginas: tipos, relações, instâncias, profundidade e o catálogo de tools.
- **Código:** é citado por marcadores no próprio código-fonte (`--8<--`). Se um trecho citado some, o build falha.
- **Catálogo do gateway:** é um arquivo versionado (`services/smoke/referencia/catalogo.json`), regenerado por `./scripts/gerar-referencia.sh`. O smoke compara esse arquivo com o gateway vivo e falha se divergirem.

## Diagramas com zoom

Todo diagrama abre num visualizador:

- os botões **+** e **−** aproximam e afastam, **⤢** enquadra e **⛶** abre em tela cheia;
- **arrastar** move o diagrama;
- **um clique** ativa o zoom pela roda do mouse, e ele se desliga ao sair do diagrama, para não atrapalhar a rolagem;
- no teclado, com o diagrama em foco, **+** e **−** aproximam e afastam e **0** enquadra;
- **"Abrir o SVG"** abre o arquivo puro, vetorial, em outra aba.

## As páginas

| Página | O que tem |
| --- | --- |
| [Arquitetura técnica](arquitetura.md) | Os três níveis C4 (contexto, containers e componentes), o que é público, o barramento e a sequência de uma viagem real |
| [O grafo de contexto](grafo.md) | O T-Box em diagrama de classes por bairro, o A-Box da Ana, as camadas de profundidade, o modelo físico no Neo4j e as consultas Cypher de cada tool |
| [O padrão do gateway MCP](gateway-mcp.md) | Como tools, skills e prompts chegam ao agente só pelo gateway, a governança em cada chamada e por que o padrão importa |
| [Skills, prompts e tools](skills-prompts-tools.md) | O formato e o ciclo de uma skill (SEP-2640), as três camadas do prompt e o catálogo completo das tools |
