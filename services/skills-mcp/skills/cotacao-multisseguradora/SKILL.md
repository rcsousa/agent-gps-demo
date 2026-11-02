---
name: cotacao-multisseguradora
description: Rota econômica do seguro residencial. Cota com as três seguradoras parceiras (Âncora, Farol e Horizonte), compara preço e coberturas e recomenda a melhor opção para a necessidade da cliente, seguindo em frente se uma delas estiver fora do ar.
allowed-tools: seguradoras.cotar_seguro contexto.consultar_estado contexto.consultar_rota risco.avaliar_adequacao
metadata:
  versao: "1.0"
  usa-skills: ""
  rota: rota-economica
---

# Cotação multisseguradora

1. `contexto.consultar_estado` com `tipo: ApiCotacao` mostra quais seguradoras estão no ar. Não cote em quem está `fora`, e diga à cliente, pelo nome, quem ficou de fora e por quê (por exemplo: "a Âncora está fora do ar agora, então comparei Farol e Horizonte").
2. `seguradoras.cotar_seguro` para cada seguradora disponível: `ancora`, `farol`, `horizonte`. Use a mesma base em todas, só de fonte confiável: `usar_laudo: true` quando o valor veio do laudo. Cada seguradora uma vez.
3. Se uma cotação falhar, registre o motivo e siga com as outras. Duas cotações já permitem comparar.
4. Monte a comparação para a cliente:

   | Seguradora | Prêmio anual | Coberturas que importam para ela | Franquias relevantes |
   | --- | --- | --- | --- |

   Se alguma seguradora ficou de fora, diga isso logo abaixo da tabela.

5. Recomende **o menor prêmio que cobre a necessidade declarada**. O mais barato só vence se cobrir o que a cliente pediu: alagamento, por exemplo, só está na Farol.
6. `risco.avaliar_adequacao` com o produto recomendado e o prêmio, antes de seguir para a proposta.
