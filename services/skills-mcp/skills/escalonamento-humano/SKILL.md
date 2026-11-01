---
name: escalonamento-humano
description: O pedágio. Quando o prêmio ou a importância segurada passam da alçada automática, envia a proposta a um especialista humano, acompanha a decisão e explica à cliente. Nenhuma emissão acima da alçada acontece sem esta aprovação.
allowed-tools: risco.verificar_alcada atendimento.solicitar_aprovacao atendimento.consultar_aprovacao contexto.consultar_regras
metadata:
  versao: "1.0"
  usa-skills: ""
  alcada: alcada-especialista
  aprovacao-humana: obrigatória
---

# Escalonamento humano

1. `risco.verificar_alcada` com o prêmio anual e a importância segurada da proposta.
   - `exige_aprovacao_humana: false`: não há pedágio; volte à rota.
2. Explique à cliente, em uma frase, que contratações desse valor passam por uma especialista e que isso protege os dois lados.
3. `atendimento.solicitar_aprovacao` com a proposta e o motivo: qual limite foi ultrapassado e por quanto.
4. Acompanhe com `atendimento.consultar_aprovacao` a cada alguns segundos, sem pressa e sem repetir a solicitação.
   - `aprovada`: guarde o `ticket_id`. Ele é o `aprovacao_id` da emissão. Diga quem aprovou.
   - `recusada`: explique à cliente com cuidado e ofereça ajustar a cobertura para caber na alçada.
5. Para mostrar a regra, `contexto.consultar_regras` com `alcada-automatica` traz a política de alçadas e a norma que a sustenta.
