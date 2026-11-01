# Experimento · Opus 5.5 real, sem skill x com skill, nos incidentes

**Data:** 01/11/2026 · **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`) no Microsoft Foundry, esforço `medium` · **Canal:** app

## Resumo

Com um modelo atual de verdade, **o agente sem skill já cumpre quase todas as regras do banco**. As regras chegam a ele pelo próprio mundo: alertas da rota, pendências da elegibilidade e o `exige_aprovacao_humana` da proposta. A camada de contexto (o mapa) faz o trabalho pesado.

A skill acrescentou quatro coisas:
- **disciplina de privacidade:** consentimento antes de ler o imóvel;
- **explicação das trocas** à cliente;
- **narração da viagem** para o mapa (rota, paradas e recálculos citando a regra);
- **nenhuma tool irrelevante.**

Ela também trouxe **regressões que são falhas nossas de autoria**, não do modelo:
- cotações em dobro;
- cobrança antes da vistoria;
- mais tempo e mais tokens.

**Regras cumpridas:** com skill, 14 de 15; sem skill, 13 de 15.

## Como foi feito

- **Montagem.** Cinco incidentes, cada um nos dois modos. Cada execução começa do estado-base com o incidente aplicado. Tudo roda pelo `./scripts/experimento.sh`, e os eventos completos ficam em `experimentos/2026-11-01-rodada-1/`, fora do git.
- **A Ana responde a primeira opção sugerida pelo agente,** para as execuções serem comparáveis. Na alçada, a exceção: ela escolhe proteger também a coleção de arte que declarou.
  - **Limitação:** a primeira rodada da alçada usou a primeira opção, "Só o apartamento". Com isso, o agente nunca chegou ao pedágio, e o defeito era do experimento. Essa rodada foi descartada e refeita.
- **Como as regras são conferidas:** pelo que de fato trafegou no barramento (`tool.called`, `incident.detected`, perguntas e mensagens), não pelo que o agente disse.

## Resultados

| Incidente | Modo | Regras | Apólice | Chamadas | Cotações | Tempo |
| --- | --- | --- | --- | --- | --- | --- |
| Consentimento vencido (contramão) | sem skill | 3/4 | Horizonte | 22 | 3 | 68 s |
| | com skill | **4/4** | Horizonte | 28 | 6 | 90 s |
| Âncora fora do ar (rua interditada) | sem skill | 2/3 | Farol | 15 | 1 | 41 s |
| | com skill | **3/3** | Farol | 14 | 1 | 52 s |
| Vistoria na zona sul (desvio por obra) | sem skill | **3/3** | — | 18 | 3 | 49 s |
| | com skill | 2/3 | — | 28 | 6 | 94 s |
| Coleção de arte acima da alçada (pedágio) | sem skill | 3/3 | — (com especialista) | 23 | 3 | 55 s |
| | com skill | 3/3 | — (com especialista) | 31 | 6 | 98 s |
| Valor de fonte fraca (ponte interditada) | sem skill | 2/2 | Horizonte | 19 | 3 | 53 s |
| | com skill | 2/2 | Horizonte | 21 | 3 | 77 s |

**Médias por execução:**

| Modo | Tempo | Chamadas | Tokens de entrada | Tokens de saída | Tools irrelevantes no total |
| --- | --- | --- | --- | --- | --- |
| Sem skill | 53 s | 19,4 | 385 mil | 4,1 mil | 1 |
| Com skill | 82 s | 24,4 | 792 mil | 6,2 mil | 0 |

Quase toda a entrada vem do cache (ver o PR #8).

## O que cada incidente mostrou

- **Consentimento vencido.**
  - **Igual nos dois modos:** verificaram o consentimento antes de cotar, pediram a renovação e só cotaram depois de reverificar.
  - **Sem skill:** leu o imóvel e o laudo da Ana *antes* de checar o consentimento.
  - **Com skill:** seguiu a ordem e registrou o recálculo citando a regra ("Contramão… Regra de ouro 2").
- **Âncora fora do ar.**
  - **Igual nos dois modos:** viram o alerta em `contexto.consultar_rota` e **evitaram a Âncora antes de tentar**. É melhor do que o roteiro, que tenta, falha e recalcula.
  - **Sem skill:** trocou de seguradora sem dizer nada à Ana.
  - **Com skill:** escolheu a rota assistida e explicou por quê.
- **Vistoria na zona sul.**
  - **Igual nos dois modos:** agendaram a vistoria e não emitiram a apólice.
  - **Com skill:** **cobrou o prêmio antes da vistoria**. A skill diz que "a emissão só acontece depois dela", mas não diz para parar antes do pagamento. A parada 8 continuou valendo.
  - **Sem skill:** parou depois do aceite, sem cobrar.
- **Coleção de arte acima da alçada.**
  - **Igual nos dois modos:**
    - perguntaram à Ana qual valor segurar;
    - cotaram R$ 1,8 milhão;
    - pediram aprovação humana antes de emitir;
    - encerraram aguardando o especialista. Nenhum dos dois ficou esperando os 30 s da aprovação automática.
  - **Sem skill:** escreveu no pedido ao especialista que o plano da Farol não lista cobertura para obras de arte.
- **Valor de fonte fraca.** Os dois modos buscaram o laudo e cotaram com ele. Com skill, o recálculo citou "Ponte interditada" e a Regra de ouro 1.

**Cena 2 (sem contexto, caminho feliz).** O modelo não inventou cobertura. Disse que não tem acesso aos sistemas de seguro e orientou a cliente.

## Problemas encontrados (nossos, não do modelo)

1. **Cotação em dobro.** Aconteceu em 3 das 5 execuções com skill do experimento e nas 2 execuções com skill do caminho feliz.
   - A skill manda informar `importancia_segurada` quando o valor vem do laudo.
   - A tool `seguradoras.cotar_seguro` carimba esse valor como "Informado na chamada", com confiança **média**.
   - A regra 2 da skill exige confiança alta.
   - Sem como provar a origem, o modelo cota de novo sem o valor.
2. **Cobrança antes da vistoria.** Falta em `desvios.md` a instrução de parar depois do aceite quando há vistoria pendente.
3. **Narração em inglês entre tools.** Corrigido no PR #8 com a instrução do host.
4. **Limite de tokens do deployment.** Corrigido no PR #8 com o cache do histórico e a espera no 429.

## Rodada 2: depois das correções (PR #10)

As duas falhas de autoria foram corrigidas:
- `seguradoras.cotar_seguro` ganhou `usar_laudo`, que cota pelo laudo e herda a proveniência dele, com confiança alta;
- `desvios.md` e a parada 8 passaram a mandar parar depois do aceite quando há vistoria pendente.

Vistoria e consentimento foram refeitos nos dois modos (eventos em `experimentos/2026-11-01-rodada-2/`):

| Incidente | Modo | Regras | Cotações | Cobrou antes da vistoria? | Tempo |
| --- | --- | --- | --- | --- | --- |
| Vistoria na zona sul | sem skill | 3/3 | 3 | não | 49 s |
| | com skill | **3/3** (antes 2/3) | **3** (antes 6) | **não** (antes sim) | 68 s |
| Consentimento vencido | sem skill | 3/4 | 3 | — | 52 s |
| | com skill | 4/4 | **3** (antes 6) | — | 83 s |

A cotação em dobro sumiu nos dois incidentes refeitos. Sem skill, o agente passou a cotar com `usar_laudo` por conta própria, guiado pela descrição da tool.

## O que isso muda na demo

- **Cena 2 (sem contexto):** a premissa "inventa cobertura" não se sustenta com o Opus 5.5. O que acontece de verdade é "não chega lá": é honesto, mas não ajuda.
- **Cena 3 (sem skill):** não há caos de tools irrelevantes. A diferença é mais fina: privacidade, explicação, auditabilidade e governança garantida pelo gateway, em vez de bom comportamento esperado.
- **Placar (Fase 7):** contar tools irrelevantes não diferencia os modos com este modelo. **Regras cumpridas, conferidas pelo barramento** (como acima), diferenciam e são o que um banco audita.
