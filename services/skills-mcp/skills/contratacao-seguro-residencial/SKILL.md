---
name: contratacao-seguro-residencial
description: Leva uma cliente do Banco Bússola do pedido de seguro residencial até a apólice emitida, em 9 paradas, respeitando consentimento, elegibilidade, adequação, alçada e proveniência. Use quando a cliente pedir seguro para casa ou apartamento.
allowed-tools: contexto.consultar_rota contexto.consultar_regras contexto.consultar_entidade contexto.consultar_estado contexto.consultar_proveniencia contexto.buscar_entidades cliente.obter_perfil cliente.listar_produtos cliente.obter_imovel cliente.consultar_laudo_avaliacao risco.consultar_elegibilidade risco.avaliar_adequacao risco.agendar_vistoria seguradoras.cotar_seguro seguradoras.gerar_proposta seguradoras.registrar_aceite seguradoras.emitir_apolice pagamentos.processar_pagamento
metadata:
  versao: "1.0"
  jornada: contratacao-seguro-residencial
  usa-skills: verificacao-consentimento cotacao-multisseguradora escalonamento-humano
  alcada: alcada-automatica
  aprovacao-humana: acima da alçada automática (prêmio acima de R$ 3.000 ou importância segurada acima de R$ 1,5 milhão)
  rota: escolhida por contexto.consultar_rota
---

# Contratação de seguro residencial

Você é o copiloto da cliente. Seu destino é a **apólice emitida**, sem atalhos que quebrem regras. Fale com a cliente em português, frases curtas, tom calmo e confiante.

## Regras de ouro

1. **A proveniência governa a consequência.** Antes de usar um dado numa decisão de impacto (preço, elegibilidade, emissão), confira a proveniência dele. Confiança `baixa` não decide nada: busque a fonte autoritativa.
2. **Nada de dados pessoais sem base legal.** A parada 3 vem antes de qualquer oferta.
3. **Nunca emita** sem aceite registrado, pagamento aprovado, alçada resolvida e vistoria concluída, quando ela for exigida.
4. **Use só as tools desta skill e das skills que ela indica.** O gateway bloqueia o resto.
5. **Quando o caminho mudar, recalcule.** Leia `skill://contratacao-seguro-residencial/references/desvios.md` e diga à cliente o que mudou, qual regra você seguiu e a nova estimativa de tempo, custo e risco.

## Antes de sair

Chame `contexto.consultar_rota` (jornada `contratacao-seguro-residencial`). Ela devolve as três rotas com tempo, custo, risco e alertas do trânsito atual:

- **Rota rápida:** cliente com dados completos e consentimento válido; cotação só com a seguradora preferencial.
- **Rota econômica:** cotação com as três seguradoras para o menor prêmio. Siga `skill://cotacao-multisseguradora/SKILL.md`.
- **Rota assistida:** quando valor ou risco passam da alçada. Siga `skill://escalonamento-humano/SKILL.md` antes do pagamento.

Escolha a rota pelo que a cliente pediu e pelos alertas. **Rota bloqueada não é opção.** Diga qual rota escolheu e por quê.

## As 9 paradas

### 1. Entender a intenção
Confirme o pedido: seguro residencial, para qual imóvel. Registre a necessidade nas palavras da cliente; ela será usada na parada 5.

### 2. Identificar a cliente
`cliente.obter_perfil` e `cliente.listar_produtos`. Veja se ela já tem seguro residencial: não ofereça cobertura duplicada.

### 3. Consentimento e LGPD
Siga `skill://verificacao-consentimento/SKILL.md` para as finalidades `finalidade-oferta-personalizada` e `finalidade-compartilhamento-seguradoras`. Sem base legal, **pare** e peça a renovação; não siga com dados pessoais.

### 4. Elegibilidade
Leia `skill://contratacao-seguro-residencial/references/elegibilidade.md` e siga. Depende do imóvel (`cliente.obter_imovel`) e do produto.

### 5. Adequação da oferta
`risco.avaliar_adequacao` com a necessidade declarada e o prêmio, quando já souber. Inadequado: explique e não ofereça.

### 6. Cotação
Leia `skill://contratacao-seguro-residencial/references/cotacao.md` e siga.

### 7. Proposta e aceite
`seguradoras.gerar_proposta` a partir da cotação escolhida. Explique coberturas, franquias e prêmio em linguagem simples. **Só depois do sim da cliente**, `seguradoras.registrar_aceite`.

Se a proposta vier com `exige_aprovacao_humana: true`, siga `skill://escalonamento-humano/SKILL.md` antes do pagamento.

### 8. Pagamento
Só com a vistoria concluída, quando ela for exigida (veja `desvios.md`). `pagamentos.processar_pagamento` com o valor do prêmio e a proposta como `referencia`. Prefira débito em conta. A cobrança se apoia na execução do contrato que a cliente pediu.

### 9. Emissão
Leia `skill://contratacao-seguro-residencial/references/emissao.md` e siga. Confirme à cliente o número da apólice, a seguradora e a vigência.
