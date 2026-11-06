# Experimento · Adequação de cada produto cotado (issue #25)

**Data:** 06/11/2026 · **Modelo:** Claude Haiku 5.5 (`claude-haiku-5-5`) no Microsoft Foundry · **Canal:** app · **Repetições:** 2 · **Custo total:** US$ 0,11

## A pergunta

Na rota econômica, o agente cota as três seguradoras. A adequação da oferta (`risco.avaliar_adequacao`) era avaliada para todos os produtos cotados, ou só para um?

## Antes da mudança

A skill `cotacao-multisseguradora` 1.0 mandava avaliar a adequação **só do produto recomendado**.

Nas execuções reais com skill e mais de uma cotação (experimentos de 01 e 02/11, com o Opus e o Haiku), **14 de 35 (40%)** avaliaram a adequação de todos os produtos cotados.

## A mudança

Na versão 1.1, a skill manda avaliar a adequação de **cada** cotação válida, com o prêmio dela, e recomendar o menor prêmio **entre as adequadas**. A proposta e o aceite continuam só da oferta escolhida pela cliente.

## Depois

Foram 3 casos que seguem a rota econômica (caminho feliz, consentimento vencido e proveniência fraca), com 2 repetições, com e sem skill.

| Modo | Execuções com mais de uma cotação | Avaliaram todos os cotados | Propostas por execução | Regras |
| --- | --- | --- | --- | --- |
| Com skill | 5 | **5 (100%)** | 1 | 30/30 |
| Sem skill | 5 | 0 | 1 | 15/30 |

- **Avaliação em dois momentos.** Com skill, o agente avalia os três produtos duas vezes em 4 das 5 execuções:
  - na **parada 5**, contra a necessidade declarada, ainda sem prêmio;
  - na **parada 6**, depois das cotações, cada um com o prêmio cotado.

  O fluxo é coerente, e cada chamada leva cerca de 20 ms. No mapa, o robô para no prédio de cada produto nas duas paradas.
- **Proposta só da oferta escolhida.** Em todas as execuções, houve uma proposta só, como a regra de negócio pede.
- **Uma execução com skill terminou sem cotar** (consentimento vencido, repetição 12). O agente verificou o consentimento logo depois de pedir a renovação, antes de o simulador confirmá-la, e encerrou com educação. Isso é anterior a esta mudança, e as regras foram todas cumpridas.

## Limitações

- São 2 repetições de 3 casos, com um modelo só.
- Os eventos completos ficam em `experimentos/2026-11-06-claude-haiku-5-5/`, fora do git.
