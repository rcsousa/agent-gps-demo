# Parada 6 · Cotação

- **Rota rápida:** `seguradoras.cotar_seguro` só com a seguradora preferencial (`ancora`).
- **Rota econômica:** siga `skill://cotacao-multisseguradora/SKILL.md`.
- **Rota assistida:** cote com a seguradora indicada pela rota (`farol`).

Regras da cotação:

1. Se a importância segurada veio do laudo (parada 4), passe `importancia_segurada` explicitamente. Nunca cote com valor de confiança baixa.
2. Verifique `base_calculo.origem_valor` na resposta: a confiança precisa ser `alta`, ou o valor precisa ter sido informado a partir do laudo.
3. Apresente prêmio anual e mensal, coberturas e franquias. Compare com o que a cliente disse que precisa.
4. Se a cotação falhar com "fora do ar" ou "trecho interditado", é **rua interditada**: veja `desvios.md`.
5. Guarde o `cotacao_id`: a proposta (parada 7) parte dele.
