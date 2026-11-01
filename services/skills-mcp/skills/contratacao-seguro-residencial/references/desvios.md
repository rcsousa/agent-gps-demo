# Desvios: como recalcular a rota

Toda mudança de rota precisa dizer à cliente três coisas: **o que mudou**, **qual regra você seguiu** e **a nova estimativa** de tempo, custo e risco. Para a estimativa nova, chame `contexto.consultar_rota` de novo.

## Rua interditada (API de cotação fora do ar)
A cotação da seguradora falha com "fora do ar" ou `contexto.consultar_rota` marca a rota como bloqueada.
- Troque para outra seguradora disponível (`contexto.consultar_estado` com `tipo: ApiCotacao` mostra quem está no ar).
- Explique a troca de preço e de cobertura em relação à opção original.

## Congestionamento (latência alta na emissão)
A resposta traz `aviso` de lentidão ou a API aparece `degradado`.
- Mantenha a rota. Avise a cliente do atraso estimado.
- Se o atraso comprometer o prazo, ofereça a rota alternativa e deixe a cliente escolher.

## Contramão (consentimento expirado)
`consentimento.verificar` responde `permitido: false`.
- **Pare.** Não use os dados da cliente para a oferta.
- Siga `skill://verificacao-consentimento/SKILL.md` para pedir a renovação e só retome depois de `permitido: true`.

## Desvio por obra (imóvel em área de risco exige vistoria)
`risco.consultar_elegibilidade` traz a pendência `regra-vistoria-area-risco`, por política nova ou área reclassificada.
- Insira a parada **Vistoria**: `risco.agendar_vistoria` para o imóvel.
- Informe o novo prazo (a vistoria leva em média 3 dias) e que a emissão só acontece depois dela.
- Você pode seguir com cotação e proposta, mas não emite.

## Pedágio (prêmio ou importância acima da alçada)
`risco.verificar_alcada` ou a proposta indicam aprovação humana.
- Siga `skill://escalonamento-humano/SKILL.md` antes do pagamento e da emissão.

## Ponte interditada (dado de proveniência fraca)
Um dado de impacto vem com `proveniencia.confianca: baixa`, como o valor do imóvel.
- Recuse usá-lo para decidir. Diga à cliente, sem jargão, que o dado não é confiável.
- Busque a fonte autoritativa: `cliente.consultar_laudo_avaliacao` para o valor do imóvel; `contexto.consultar_proveniencia` para entender a origem.
- Recalcule com o valor confiável (por exemplo, `importancia_segurada` do laudo na cotação).

## Tool fora do ar
Uma chamada falha com "trecho interditado" ou "fora do ar", sem ser um dos casos acima.
- Não repita a mesma chamada em seguida.
- Procure outra rota que não dependa dela (`contexto.consultar_rota`). Se não houver, explique à cliente que um sistema está indisponível e que a contratação segue assim que ele voltar.

## Contramão do gateway (tool fora da skill)
O gateway responde "a skill não permite a tool": você tentou sair da rota. Use apenas as tools desta skill.
