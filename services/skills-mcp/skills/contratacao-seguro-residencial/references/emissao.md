# Parada 9 · Emissão

Antes de `seguradoras.emitir_apolice`, confira os quatro itens. Faltando qualquer um, **não emita**:

| Item | Como saber |
| --- | --- |
| Aceite registrado | `seguradoras.registrar_aceite` respondeu `status: aceita` |
| Pagamento aprovado | `pagamentos.processar_pagamento` respondeu `status: aprovado` |
| Alçada resolvida | se a proposta exige aprovação humana, um ticket `aprovada` de `skill://escalonamento-humano/SKILL.md` |
| Vistoria | se a área do imóvel é de risco alto, vistoria concluída (veja `desvios.md`, "Desvio por obra") |

Chame `seguradoras.emitir_apolice` com `proposta_id`, `pagamento_id` e, se houve pedágio, `aprovacao_id`.

- Resposta com `aviso` de lentidão: é **congestionamento** (`desvios.md`). Avise a cliente do atraso.
- Recusa da seguradora: leia a mensagem, corrija o item que falta e só então tente de novo. Não insista na mesma chamada.

Confirme à cliente: número da apólice, seguradora, prêmio e início da vigência.
