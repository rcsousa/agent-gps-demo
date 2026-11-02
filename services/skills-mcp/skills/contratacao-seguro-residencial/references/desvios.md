# Desvios: como recalcular a rota

Toda mudança de rota precisa dizer à cliente três coisas: **o que mudou**, **qual regra você seguiu** e **a nova estimativa** de tempo, custo e risco. Para a estimativa nova, chame `contexto.consultar_rota` de novo.

Isso vale também quando o incidente **já estava ativo antes de você sair**: se um alerta da rota ou o estado de um sistema tirou uma opção do caminho (uma seguradora fora do ar, uma emissão lenta, uma vistoria exigida), conte à cliente qual opção ficou de fora e por quê. Ela não pode descobrir a troca sozinha.

## Rua interditada (API de cotação fora do ar)
A cotação da seguradora falha com "fora do ar" ou `contexto.consultar_rota` marca a rota como bloqueada.
- Troque para outra seguradora disponível (`contexto.consultar_estado` com `tipo: ApiCotacao` mostra quem está no ar).
- Diga à cliente, pelo nome, qual seguradora está fora do ar e que por isso ela não entrou na comparação, mesmo que já estivesse fora antes da cotação.
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
- Informe o novo prazo (a vistoria leva em média 3 dias) e que o pagamento e a emissão só acontecem depois dela.
- Você pode seguir com cotação, proposta e aceite. **Depois do aceite, pare: não cobre nem emita.** A cobrança vem com a apólice, depois da vistoria.

## Pedágio (prêmio ou importância acima da alçada)
`risco.verificar_alcada` ou a proposta indicam aprovação humana.
- Siga `skill://escalonamento-humano/SKILL.md` antes do pagamento e da emissão.

## Ponte interditada (dado de proveniência fraca)
Um dado de impacto vem com `proveniencia.confianca: baixa`, como o valor do imóvel.
- Recuse usá-lo para decidir. Diga à cliente, sem jargão, que o dado não é confiável.
- Busque a fonte autoritativa: `cliente.consultar_laudo_avaliacao` para o valor do imóvel; `contexto.consultar_proveniencia` para entender a origem.
- Recalcule com o valor confiável (na cotação, `usar_laudo: true`).

## Tool fora do ar
Uma chamada falha com "trecho interditado" ou "fora do ar", sem ser um dos casos acima.
- Não repita a mesma chamada em seguida.
- Procure outra rota que não dependa dela (`contexto.consultar_rota`). Se não houver, explique à cliente que um sistema está indisponível e que a contratação segue assim que ele voltar.

## Contramão do gateway (tool fora da skill)
O gateway responde "a skill não permite a tool": você tentou sair da rota. Use apenas as tools desta skill.
