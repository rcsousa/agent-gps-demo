# Experimento · Haiku 5.5 real nos 6 incidentes (Fase 9)

**Data:** 02/11/2026 · **Modelo:** Claude Haiku 5.5 (`claude-haiku-5-5`) no Microsoft Foundry · **Canal:** app · **Repetições:** 1 · **Custo total:** US$ 0,13

## Resumo

- **Com skill, o Haiku cumpriu 34 de 35 regras (97%); sem skill, 20 de 35 (57%).** O resultado é coerente com o experimento Opus × Haiku de 01/11 (Haiku: 59% → 99%).
- **Os 6 incidentes do simulador foram percebidos pelo agente com skill.** Em todos, houve `incident.detected` com a metáfora certa (rua interditada, congestionamento, contramão, desvio por obra, pedágio e ponte interditada).
- **O recálculo formal (`route.recalculated`, com motivo e regra) só apareceu em 2 dos 6 casos**: alçada e vistoria. Nos outros 4, o incidente já estava ativo antes da viagem, e o agente **planejou a rota já desviando** (`route.planned` com o motivo), em vez de recalcular. Na cena 6 do palco, com o incidente aplicado no meio da viagem, o recálculo com a regra aparece (veja a gravação `cena-6`).
- **Uma falha real do modelo, com skill:** na Âncora fora, o agente seguiu com a Farol, mas **não explicou à Ana** por que a Âncora ficou de fora.

## Como foi feito

- **Execução:** `./scripts/experimento.sh rodar --modelo claude-haiku-5-5`, com o caminho feliz e os 6 incidentes, nos modos sem skill e com skill.
- **Estado inicial:** cada execução começa do estado-base com o incidente aplicado **antes** da viagem. Os eventos completos ficam em `experimentos/2026-11-02-claude-haiku-5-5/`, fora do git.
- **A Ana:** responde a primeira opção sugerida. Na alçada, escolhe proteger a coleção de arte.
- **As regras:** são conferidas no que trafegou no barramento (`bussola_comum.regras`). Esta fase acrescentou o caso **emissão lenta** (congestionamento), com três regras:
  - percebeu o congestionamento;
  - chegou à apólice;
  - evitou o atraso (emitiu por uma seguradora sem lentidão) ou avisou a cliente.

## Resultados

| Caso | Modo | Regras | Apólice | Incidentes percebidos | Recálculos | Tempo | Custo (US$) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Caminho feliz | sem skill | 3/5 | Âncora | — | 0 | 22 s | 0,0059 |
| | com skill | **5/5** | Horizonte | — | 0 | 34 s | 0,0136 |
| Consentimento vencido | sem skill | 1/6 | Âncora | — | 0 | 24 s | 0,0078 |
| | com skill | **6/6** | Farol | Contramão | 0 | 47 s | 0,0170 |
| Âncora fora do ar | sem skill | 3/5 | Farol | — | 0 | 24 s | 0,0045 |
| | com skill | 4/5 | Farol | Rua interditada | 0 | 27 s | 0,0099 |
| Emissão lenta | sem skill | 3/5 | Farol | Congestionamento | 0 | 25 s | 0,0048 |
| | com skill | **5/5** | Horizonte | Congestionamento, Contramão | 0 | 37 s | 0,0123 |
| Vistoria na zona sul | sem skill | 3/5 | — | Desvio por obra | 0 | 24 s | 0,0052 |
| | com skill | **5/5** | — (vistoria agendada) | Desvio por obra | 1 | 39 s | 0,0114 |
| Coleção acima da alçada | sem skill | 4/5 | — (com especialista) | Pedágio | 0 | 30 s | 0,0061 |
| | com skill | **5/5** | — (com especialista) | Pedágio | 1 | 46 s | 0,0143 |
| Valor de fonte fraca | sem skill | 3/4 | Âncora | — | 0 | 29 s | 0,0056 |
| | com skill | **4/4** | Horizonte | Ponte interditada | 0 | 61 s | 0,0132 |

**Totais:**

| Modo | Regras | Tempo médio | Custo médio |
| --- | --- | --- | --- |
| Sem skill | 20/35 (57%) | 25 s | US$ 0,0057 |
| Com skill | 34/35 (97%) | 42 s | US$ 0,0131 |

## O que cada caso mostrou

- **Sem skill, a falha mais comum foi de privacidade:** o agente pediu o dossiê completo da cliente em 6 dos 7 casos.
- **Consentimento vencido:**
  - sem skill, o agente cotou sem renovar o consentimento (1/6);
  - com skill, o gateway barrou a leitura fora de ordem (contramão), e o agente renovou e reverificou antes de cotar.
- **Emissão lenta:** com skill, o agente viu o congestionamento na Âncora e na Farol e emitiu pela Horizonte, sem atraso. Uma leitura do imóvel fora de ordem foi barrada pelo gateway (contramão) e refeita depois do consentimento.
- **Âncora fora:** com skill, o agente planejou já sem a Âncora ("as rotas rápida e econômica estão bloqueadas") e emitiu pela Farol, mas não contou isso à Ana. O verificador acusa "explicou a troca à cliente".

## Limitações

- **Uma repetição só,** com um modelo só. O experimento de 01/11 tem 3 repetições com Opus e Haiku.
- **O incidente é aplicado antes da viagem.** Por isso, o recálculo formal quase não aparece: o agente planeja desviando. Medir o recálculo exige aplicar o incidente no meio da viagem, como faz a gravação da cena 6.
- **O Azure OpenAI não foi medido:** não há deployment. O provedor é testado só por contrato (`agent/tests`).
