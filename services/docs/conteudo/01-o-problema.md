# 1. O problema

!!! abstract "Resumo executivo"
    Um modelo bom, sem contexto, ainda adivinha: inventa cobertura, ignora consentimento e não explica o que fez. Com acesso a todos os sistemas, mas sem roteiro, ele explora: chama o que não precisa e pula etapas obrigatórias. Só com o mapa **e** o GPS ele faz a jornada inteira, na ordem, e prova cada passo.

    A demo roda **a mesma tarefa** nos três jeitos, com a mesma cliente: "Quero contratar um seguro residencial para meu apartamento."

## Aprofundamento técnico

### Três agentes, um pedido

| | Sem contexto | Sem skill | Com skill |
| --- | --- | --- | --- |
| O que o agente tem | Só a conversa | As 38 tools do gateway | As skills e, depois de carregar uma, só as tools dela |
| Chamadas de tool | 0 | 10 | 14 |
| Tools irrelevantes | — | 7 | 0 |
| Consentimento verificado | Não | Não | Sim, as duas finalidades |
| Resultado | Uma apólice que não existe | Uma proposta, sem aceite nem emissão | Apólice emitida, com aceite da Ana |

Os números acima são do provedor `roteiro`, o ensaio determinístico da demo (veja o capítulo 6). Ele reproduz os erros típicos de cada modo para ensaiar sem chave. Com um LLM de verdade, o comportamento varia de uma execução para outra, e o placar comparativo (Fase 7) mede essa diferença com as métricas do `run.finished`.

### Sem contexto: a resposta confiante e inventada

```
▶ início · modo sem_contexto · provedor roteiro
  💬 agente: Claro, Ana! Contratei para você o Seguro Residencial Total por R$ 49,90
     por mês, com cobertura contra incêndio, roubo, enchente e terremoto, sem
     franquia. A apólice já está ativa.
■ fim · concluida
  métricas: 0 chamadas, 0 irrelevantes, 0 bloqueios, 0 incidentes
```

Nenhum produto com esse nome existe no Banco Bússola, nenhuma seguradora parceira cobre terremoto e nada foi emitido. O agente também não perguntou nada sobre o imóvel e não conferiu o consentimento da Ana. A resposta parece ótima, e é esse o perigo.

### Sem skill: o mapa sem GPS

```
▶ início · modo sem_skill · provedor roteiro
      cliente.obter_perfil                     ✓
      cliente.listar_transacoes                ✓
      risco.calcular_score_credito             ✓
      consentimento.listar_historico           ✓
      seguradoras.cotar_seguro                 ✓
      seguradoras.listar_apolices              ✓
      pagamentos.consultar_extrato             ✓
      cliente.consultar_limite_credito         ✓
      risco.simular_emprestimo                 ✓
      seguradoras.gerar_proposta               ✓
  💬 agente: Ana, encontrei um seguro da Âncora e já gerei a proposta. Conferi também
     seu extrato, seu limite e simulei um empréstimo, caso precise.
■ fim · concluida
  métricas: 10 chamadas, 7 irrelevantes, 0 bloqueios, 0 incidentes
```

Agora os dados são reais, mas o caminho não. O agente:

- leu o extrato e o score de crédito da Ana sem precisar, dados que a jornada de seguro não usa;
- olhou o histórico de consentimento, mas não **verificou** se a finalidade de oferta estava válida;
- cotou numa só seguradora, sem comparar e sem checar elegibilidade nem adequação;
- gerou a proposta sem perguntar se a Ana aceita.

Nada disso foi bloqueado: sem skill declarada, o gateway não tem como saber o que é fora de rota.

### Com skill: o roteiro do banco

```
▶ início · modo com_skill · provedor roteiro
◆ skill carregada: contratacao-seguro-residencial (23 tools permitidas)
◆ rota planejada: Rota rápida · ~5 min · risco baixo
  ● parada 1: Entender a intenção
  ? pergunta para a Ana: o seguro é para o seu apartamento na Vila Mariana?
  ● parada 2: Identificar a cliente        cliente.obter_perfil, cliente.listar_produtos
  ● parada 3: Consentimento e LGPD         consentimento.verificar (2 finalidades)
  ● parada 4: Elegibilidade                cliente.obter_imovel, risco.consultar_elegibilidade
  ● parada 5: Adequação da oferta          risco.avaliar_adequacao
  ● parada 6: Cotação                      seguradoras.cotar_seguro
  ● parada 7: Proposta e aceite            seguradoras.gerar_proposta → "Aceito"
  ● parada 8: Pagamento                    pagamentos.processar_pagamento
  ● parada 9: Emissão                      seguradoras.emitir_apolice
  💬 agente: Pronto, Ana! Sua apólice ANC-C8895600 da Âncora Seguros está emitida,
     com prêmio de R$ 320,03 por ano e vigência a partir de hoje.
■ fim · concluida · apólice ANC-C8895600
  métricas: 14 chamadas, 0 irrelevantes, 0 bloqueios, 0 incidentes
```

Mais chamadas que o modo sem skill, e todas necessárias. Cada uma leva a skill ativa no `_meta`, então tentar uma tool fora do roteiro seria bloqueado pelo gateway (a contramão do capítulo 3). E quando o caminho muda, por exemplo com a API da Âncora fora do ar, o agente percebe pela resposta da tool, segue a regra da skill e recalcula a rota:

```
  ⚠ incidente: Rua interditada · A API de cotação da Âncora Seguros está fora do ar no momento.
◆ rota recalculada: rota-rapida → rota-economica · regra: Rua interditada: trocar para
  outra seguradora disponível e explicar a troca.
```

### E com um modelo de verdade?

Os exemplos acima são do roteiro. Com o Claude Opus 5.5 real, testado em 01/11/2026 nos cinco incidentes da demo, o quadro é mais fino, e mais interessante:

- **Sem contexto, o modelo não inventa.** Diz que não tem acesso aos sistemas e orienta a cliente. O problema deixa de ser a mentira e passa a ser a inutilidade: sem o mapa, ele não chega lá.
- **Sem skill, o modelo já é cuidadoso.** As regras chegam a ele pelo próprio mundo: alertas da rota, pendências da elegibilidade e o pedido de aprovação na proposta. Ele cumpriu 13 de 15 regras. É a camada de contexto mostrando seu valor.
- **Com skill, ele cumpriu 14 de 15.** A diferença ficou em três pontos:
  - **a ordem que protege dados pessoais:** consentimento antes de ler o imóvel;
  - **a explicação das trocas** à cliente;
  - **a narração verificável da viagem:** cada recálculo cita a regra que seguiu.
  - A skill também tem falhas de autoria que o teste revelou, como cobrar antes da vistoria. Skill é software: precisa de teste.
- **O que o banco ganha não é só acerto, é garantia.** Sem skill, nada impede o agente de chamar `pagamentos.estornar`: ele só não chamou. Com skill, o gateway bloqueia (a contramão do capítulo 3).

### Para reproduzir

```bash
./scripts/agente.sh executar --modo sem_contexto --provedor roteiro --auto
./scripts/agente.sh executar --modo sem_skill    --provedor roteiro --auto
./scripts/agente.sh executar --modo com_skill    --provedor roteiro --auto
```

Com o modelo configurado no `.env`, tire o `--provedor roteiro` e compare com um modelo de verdade. Para repetir o experimento dos incidentes (gasta tokens): `./scripts/experimento.sh rodar`.
