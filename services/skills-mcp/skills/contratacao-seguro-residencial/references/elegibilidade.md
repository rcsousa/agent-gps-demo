# Parada 4 · Elegibilidade

1. `cliente.obter_imovel` para o imóvel da cliente. **Confira `proveniencia.confianca`.**
   - `alta`: siga.
   - `media` ou `baixa`: o valor não pode decidir elegibilidade nem preço. Chame `cliente.consultar_laudo_avaliacao` (fonte autoritativa) e use o `valor_avaliado` dali em diante. Se não houver laudo, explique à cliente que precisamos de uma avaliação antes de seguir.
2. `risco.consultar_elegibilidade` com a cliente e o produto da seguradora da rota escolhida.
3. Leia o resultado regra a regra:
   - `falhas` não vazias: o produto não serve. Explique a regra em uma frase e tente outra seguradora, se a falha for do produto (região, valor máximo, construção).
   - `pendencias` com `regra-vistoria-area-risco`: **desvio por obra**. Veja `desvios.md`, item "Desvio por obra".
4. Na dúvida sobre uma regra, `contexto.consultar_regras` com o id do produto mostra a regra, a norma que a sustenta e a proveniência.
