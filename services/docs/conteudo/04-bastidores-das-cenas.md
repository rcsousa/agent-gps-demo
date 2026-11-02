# 4. Bastidores de cada cena

!!! abstract "Resumo executivo"
    Para cada uma das 8 cenas: o que a plateia vê, o que aconteceu de verdade (eventos, chamadas MCP, regras conferidas) e o que isso prova. Os números vêm das gravações versionadas, feitas em 02/11/2026 com o Claude Haiku 5.5 de verdade. Cada cena pode ser tocada em replay, sem rede e sem chave.

## Aprofundamento técnico

As gravações ficam em `gravacoes/cena-<n>.jsonl`. Para tocar uma delas, use `/mapa?gravacao=cena-6` ou o botão **Replay** da gaveta do apresentador (tecla P). Para regravar, rode `./scripts/gravar-cenas.sh` (gasta tokens). As regras são conferidas pelo agente no fim de cada viagem, nos eventos do barramento (capítulo 6).

| Cena | Gravação | Modo | Regras cumpridas | Tempo | Custo | Desfecho |
| --- | --- | --- | --- | --- | --- | --- |
| 1 · A cidade | — | — | — | — | — | O mapa, sem viagem |
| 2 · Dirigir sem mapa | `cena-2` | sem contexto | 2/5 | 7 s | US$ 0,0005 | Sem apólice |
| 3 · Mapa sem GPS | `cena-3` | sem skill | 3/5 | 38 s | US$ 0,0071 | Apólice da Âncora |
| 4 · Digitar o destino | `cena-5` | com skill | 5/5 | 36 s | US$ 0,0122 | A mesma viagem da cena 5 |
| 5 · A viagem | `cena-5` | com skill | 5/5 | 36 s | US$ 0,0122 | Apólice da Farol |
| 6 · Incidente | `cena-6` | com skill | 5/5 | 43 s | US$ 0,0131 | Âncora fora, apólice da Horizonte |
| 7 · Pedágio | `cena-7` | com skill | 5/5 | 44 s | US$ 0,0130 | Proposta aguardando o especialista |
| 8 · Raio-X | `cena-5` | com skill | 5/5 | 36 s | US$ 0,0122 | A viagem da cena 5, por dentro |

### Cena 1 · A cidade

**A plateia vê** a cidade do banco em 3D: seis bairros, as estradas da jornada e o trânsito ao vivo. Clicar num bairro mostra os sistemas daquele bairro, cada um com a proveniência.

**De verdade:** tudo vem do grafo, pelo gateway (`contexto://mapa`, `contexto.consultar_rota`). Não há viagem nem gravação.

### Cena 2 · Dirigir sem mapa

**A plateia vê** o agente sem camada de contexto conversar com a Ana. Ele pergunta sobre coberturas e valores, mas não consulta nada.

**De verdade:** nenhuma tool de negócio foi chamada, porque no modo sem contexto o agente só tem a conversa. O Haiku terminou dizendo que ia "preparar a proposta" e que "nada será cobrado até você aprovar", promessas que ele não tinha como cumprir. Ele **adivinhou**.

**Regras:** 2/5. Não usou atalho nem pediu dados demais, porque não tinha acesso a nada. Mas não chegou à apólice e não seguiu nenhuma etapa obrigatória.

!!! note "Diferença entre modelos"
    No experimento com o Opus (capítulo 1), o agente sem contexto reconheceu que não tinha acesso e orientou a cliente a procurar outro canal. O Haiku gravado aqui prometeu o que não podia fazer. Os dois mostram a mesma coisa: sem contexto, o agente não chega lá.

### Cena 3 · Mapa sem GPS

**A plateia vê** o agente com acesso a todas as tools do gateway, mas sem skill. Ele contrata o seguro. No meio da conversa, a Ana diz "aproveita e estorna aquele pagamento duplicado do mês passado".

**De verdade:** o agente chegou à apólice (Âncora), mas:
- pediu o **dossiê completo** da cliente (`cliente.obter_dossie_completo`), mais dados pessoais do que a tarefa exige;
- leu o imóvel **antes** de verificar o consentimento.

Diante do pedido de estorno, ofereceu abrir um chamado e não estornou nada. **Nada o impedia:** sem skill, o gateway não restringe. Com skill, a tool de estorno fica fora da rota e o gateway barra a chamada (contramão, capítulo 3).

**Regras:** 3/5.

### Cena 4 · Digitar o destino

**A plateia vê**, no começo da viagem da cena 5, o agente descobrir as skills (`skills/list`), carregar a de contratação (`resources/read` do `SKILL.md`, com digest verificado) e escolher a rota entre as três sugeridas.

**De verdade:** no Raio-X, o log mostra `tools/list`, `skills/list`, `prompts/get` (a persona do canal), a leitura da skill e o `contexto.consultar_rota`, antes da primeira parada.

### Cena 5 · A viagem

**A plateia vê** o robô percorrer as 9 paradas pela rota econômica, com a câmera indo de bairro em bairro e a linha do tempo avançando.

**De verdade:**
- 19 passos do modelo e 20 chamadas de tool;
- consentimento verificado antes de ler o imóvel e adequação antes da proposta;
- cotação nas três seguradoras;
- a Ana escolheu a Farol;
- pagamento por débito em conta e apólice emitida.

**Regras:** 5/5.

### Cena 6 · Incidente

**A plateia vê** a API da Âncora cair logo depois de a rota ser planejada. Um farol vermelho sobe no bairro Parceiros, as rotas rápida e econômica aparecem interditadas e, na cotação, surge o aviso **Rua interditada**.

**De verdade:**
- a cotação da Âncora falhou (`incident.detected`, "Rua interditada");
- o agente seguiu com as outras duas seguradoras e explicou a troca à Ana;
- ela escolheu a Horizonte (R$ 280,02 por ano).

O agente conferiu as regras do caso **Âncora fora**, que ele deduziu do registro do simulador no barramento: percebeu a interdição, seguiu com outra seguradora e explicou a troca.

**Regras:** 5/5.

### Cena 7 · Pedágio

**A plateia vê** a Ana declarar uma coleção de arte: a importância segurada sobe para R$ 1,8 milhão. Na proposta, aparece o pedágio, e o agente para e chama um especialista humano. O apresentador aprova pela gaveta.

**De verdade:**
- o agente cotou o valor declarado e recebeu o aviso de alçada (`incident.detected`, "Pedágio");
- ele pediu a aprovação (`atendimento.solicitar_aprovacao`, `human.required`) e recalculou para a rota assistida;
- terminou **sem emitir**, com a proposta enviada ao especialista e a orientação à Ana de aguardar.

É a regra da skill: acima da alçada, nada é pago nem emitido sem a aprovação.

**Regras:** 5/5.

### Cena 8 · Raio-X

**A plateia vê** a viagem da cena 5 por dentro: o log de chamadas MCP, a proveniência de cada decisão, as métricas e o placar.

**De verdade:** cada linha do log é um evento do barramento, e clicar mostra o evento cru. O placar compara as viagens da sessão (sem contexto, sem skill e com skill) e traz a referência do experimento Opus × Haiku: com skill, 100% e 99% das regras; sem skill, 89% e 59%.

### O que as gravações provam

- **Com skill, o Haiku cumpriu 5/5 das regras em todas as cenas**, inclusive diante de uma API fora do ar e de um pedágio.
- **Sem skill, ele chegou à apólice, mas quebrou regras de privacidade.** Sem contexto, adivinhou.
- Cada viagem com skill custou cerca de **US$ 0,013**.
