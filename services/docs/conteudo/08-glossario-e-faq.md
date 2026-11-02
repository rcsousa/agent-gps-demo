# 8. Glossário e perguntas frequentes

!!! abstract "Resumo executivo"
    Aqui estão os termos explicados para o público executivo e respostas diretas às objeções técnicas mais comuns, como "isso é real ou é animação?".

## Aprofundamento técnico

### A metáfora: mapa, trânsito, regras e GPS

Cada elemento da navegação tem um equivalente técnico. É a mesma tabela do infográfico de abertura, com a peça da demo que a implementa:

| Navegação | Camada de contexto | Onde está na demo |
| --- | --- | --- |
| Mapa (bairros, ruas, pontos de interesse) | Ontologia e grafo de conhecimento: entidades, sistemas, produtos e relações | Neo4j, lido pelo `contexto-mcp` (`contexto://mapa`) |
| Trânsito em tempo real | Estado vivo: disponibilidade de APIs, latência, filas e eventos | Status dos nós, mudado pelo `simulator`; os faróis do Modo Mapa |
| Regras de trânsito (contramão, rodízio, pedágio) | Governança: permissões, políticas, consentimento e limites de risco | `workflow.yaml` da skill, aplicado pelo `mcp-gateway`; aprovação de alçada |
| GPS | A skill: o procedimento que diz como ir de A a B usando o mapa | `skills-mcp` (SEP-2640) |
| Zoom do mapa | Divulgação progressiva: carrega o detalhe só quando precisa | O bairro que se abre no Modo Mapa; as referências da skill lidas sob demanda |
| Rotas alternativas | Planos alternativos com custo, tempo e risco | `contexto.consultar_rota` e o cartão de rotas |
| Recálculo de rota | Replanejamento diante de um incidente | `route.recalculated`, com motivo e regra |
| Alertas da comunidade | Telemetria e feedback de outros agentes | Alertas das rotas e o barramento de eventos |
| Destino | O objetivo do cliente | O pedido da Ana: o seguro residencial |
| Histórico da viagem | Proveniência: de onde veio cada decisão | Proveniência dos nós e os eventos da execução (Modo Raio-X, Fase 7) |

### Isso é real ou é animação?

**É real.** Toda animação do Modo Mapa corresponde a um evento do barramento, emitido pelo agente ou pelo gateway durante a execução.

O mapa pode mostrar um evento alguns segundos **depois** de ele acontecer. O diretor de animações reproduz os eventos na ordem, com um tempo mínimo para cada um, para que a plateia consiga acompanhar. **Ele nunca cria um evento nem muda a ordem.** O selo "Reproduzindo" indica quando o mapa está atrás do agente, e "Pular para o fim" alcança o presente.

!!! note "Em construção"
    O glossário completo e as demais perguntas frequentes vão ser escritos na Fase 8 (bastidores).
