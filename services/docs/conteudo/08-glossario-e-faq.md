# 8. Glossário e perguntas frequentes

!!! abstract "Resumo executivo"
    Os termos da demo em uma frase cada, e respostas diretas às perguntas que a plateia técnica costuma fazer, de "isso é real ou é animação?" a "quanto custa?". Cada resposta aponta o capítulo que mostra os detalhes.

## Aprofundamento técnico

### Glossário

| Termo | Em uma frase |
| --- | --- |
| **Agente** | Um modelo de linguagem que, além de conversar, usa ferramentas para fazer coisas: consultar o cadastro, cotar, cobrar. |
| **MCP** (Model Context Protocol) | O padrão aberto pelo qual o agente descobre e chama ferramentas, lê arquivos e recebe instruções, de qualquer fornecedor. |
| **Servidor MCP** | Um serviço que oferece ferramentas por MCP. Na demo, cada área do banco (cliente, risco, seguradoras...) é um. |
| **Gateway** | O ponto único pelo qual o agente fala com todos os servidores. É ali que as regras são aplicadas e tudo é registrado. |
| **Tool** (ferramenta) | Uma ação que o agente pode pedir, como `seguradoras.cotar_seguro`. Para o mapa, é uma rua até um sistema. |
| **Skill** | O roteiro de uma tarefa: quais ferramentas usar, em que ordem e o que fazer quando algo dá errado. É o GPS. |
| **SEP-2640** | A proposta de extensão do MCP que permite servir skills (`skills/list`, `skills/get`) como qualquer outro recurso. |
| **Camada de contexto** | O que o banco sabe sobre si mesmo, num formato que o agente consegue usar: o mapa, o trânsito e as regras. |
| **Ontologia** | O "dicionário" do mapa: que tipos de coisa existem (cliente, apólice, regra) e como podem se ligar. |
| **Grafo** | O mapa em si: as coisas concretas (a Ana, o apartamento dela, a API da Âncora) e as ligações entre elas. |
| **Estado vivo** | O trânsito: o que está no ar, lento ou fora agora. Muda enquanto a demo roda. |
| **Proveniência** | De onde veio um dado ou uma regra: a fonte, a data, quem é o responsável e quanta confiança ela merece. |
| **Alçada** | O limite até onde uma decisão é automática. Acima dele, só com aprovação de uma pessoa. |
| **Pedágio** | A parada obrigatória para essa aprovação humana. |
| **Contramão** | Uma ferramenta chamada fora da skill ou fora de ordem. O gateway barra. |
| **Recálculo** | Trocar de rota no meio da viagem porque algo mudou, dizendo o motivo e a regra. |
| **Replay** | Tocar uma viagem gravada, sem rede e sem modelo, sempre com o selo "Replay" visível. |
| **Placar** | A comparação entre os modos pelas regras do banco que cada viagem cumpriu, conferidas nos eventos. |
| **Cache de prompt** | Reaproveitar a parte da conversa que não mudou entre uma chamada e outra ao modelo. Corta o custo em cerca de 80%. |

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
| Histórico da viagem | Proveniência: de onde veio cada decisão | Proveniência dos nós e os eventos da execução, no Modo Raio-X |

### Isso é real ou é animação?

**É real.** Toda animação do Modo Mapa corresponde a um evento do barramento, emitido pelo agente ou pelo gateway durante a execução. No Modo Raio-X, cada linha do log abre o evento cru.

O mapa pode mostrar um evento alguns segundos **depois** de ele acontecer. O diretor de animações reproduz os eventos na ordem, com um tempo mínimo para cada um, para que a plateia consiga acompanhar. **Ele nunca cria um evento nem muda a ordem.** O selo "Reproduzindo" indica quando o mapa está atrás do agente, e "Pular para o fim" alcança o presente. Veja o [capítulo 6](06-arquitetura.md#o-diretor-de-animacoes).

### E se a rede cair, ou a chave do modelo não funcionar no dia?

**As cenas tocam em replay.** Cada uma foi gravada de uma execução real com o Haiku (`gravacoes/`, no repositório). O replay não usa rede, chave nem LLM: o agente serve os eventos gravados, no ritmo original, e o mapa e o Raio-X os desenham como numa viagem ao vivo. A diferença fica sempre visível no selo "Replay · gravado em … com …".

### Quem pode acessar a demo?

**Só quem tem login.** Nenhuma parte da experiência abre sem sessão. Os usuários ficam no `.env` do servidor, criados com `./scripts/criar-usuario.sh`, e o Neo4j não é publicado na rede. Veja o [capítulo 6](06-arquitetura.md#login-nenhuma-parte-da-demo-sem-sessao).

### E numa rede corporativa, com proxy ou antivírus?

**A viagem segue por outro caminho.** Os eventos chegam ao mapa por SSE, um stream que só termina no fim da viagem. Proxies e antivírus com inspeção de HTTPS costumam segurar a resposta inteira, e aí nada chega. Se nenhum evento aparecer em 4 s, o mapa passa sozinho para a consulta por lotes, com os mesmos eventos e até 2 s de atraso, e mostra o selo "Eventos por consulta". Se a rede do evento for conhecida por isso, abra o mapa com `?eventos=consulta` para pular a espera. Veja o [capítulo 6](06-arquitetura.md#eventos-ate-o-navegador-sse-com-alternativa-por-consulta).

### Como o placar sabe que uma regra foi cumprida?

**Pelos eventos, não pelo que o agente diz.** No fim de cada viagem, o agente lê do barramento tudo o que ela fez, inclusive o que o gateway registrou, e confere as regras do caso. Por exemplo: o consentimento foi verificado antes de ler o imóvel? Houve aprovação humana antes de emitir? Uma tentativa barrada pelo gateway não conta como feita. É o mesmo verificador do experimento com o modelo real.

### Por que não colocar tudo no prompt?

Porque o banco é grande demais e muda o tempo todo. Um prompt com todas as regras, produtos e sistemas ficaria enorme, caro e desatualizado no dia seguinte. Com a camada de contexto, o agente **consulta** o que precisa, quando precisa (o zoom do mapa), e o estado vivo chega na hora. E uma regra no prompt é um pedido; no gateway, é uma **garantia**: a contramão é barrada mesmo que o modelo tente. Veja os capítulos [2](02-camada-de-contexto.md) e [3](03-skills-como-gps.md).

### O gateway não vira gargalo?

Ele faz pouco por chamada: confere a skill e a ordem (uma consulta ao Redis) e repassa ao servidor certo. Na demo, isso soma milissegundos a chamadas que levam dezenas ou centenas, como mostra a aba Métricas do Raio-X. Em produção, o gateway é um serviço sem estado próprio (o estado fica no Redis) e escala horizontalmente, como qualquer API gateway.

### E se o modelo errar mesmo com a skill?

Acontece, e o placar mostra. No experimento com 36 execuções por modelo, o Haiku com skill cumpriu 99% das regras: errou uma de noventa. O que a skill garante não é que o modelo acerte tudo. Ela garante que **o que é proibido não passa**: fora da skill ou fora de ordem, o gateway barra. O erro que sobra é de qualidade (uma explicação mais fraca, por exemplo), não de risco. Veja o [capítulo 1](01-o-problema.md#e-com-um-modelo-de-verdade).

### Quanto custa?

Uma contratação completa com o Haiku e a skill custa cerca de **US$ 0,012 a 0,013**, ou uns US$ 12 por mil contratações. Com o Opus, cerca de US$ 0,52. O cache de prompt corta o custo em cerca de 80% nos dois. Cada viagem mostra o custo real no fim, e o placar compara os modelos. Veja o [capítulo 1](01-o-problema.md) e o experimento em `docs/experimentos/`.

### Dá para usar outro modelo?

Sim. O agente tem uma interface única de LLM: Anthropic (na API ou no Microsoft Foundry) ou Azure OpenAI, escolhidos por variável de ambiente, sem mudar nenhum fluxo. Entre os modelos Claude configurados, a barra do mapa escolhe o modelo de cada viagem. Veja o [capítulo 6](06-arquitetura.md#como-trocar-o-provedor-de-llm).

### Isso funciona com sistemas legados?

Funciona. Cada sistema entra como um servidor MCP: uma camada fina que traduz a API (ou o banco de dados, ou a fila) existente em ferramentas com nome e contrato claros. O sistema legado não muda. Na demo, as APIs das seguradoras e o core bancário são exatamente isso. E os "atalhos legados" (a contratação expressa, a cotação v1) mostram o outro lado: sem skill, o agente pode usá-los; com skill, ficam fora da rota.

### Como o banco audita o que o agente fez?

Pelo barramento: cada chamada de ferramenta, leitura de skill, passo do modelo, decisão de rota e resposta da cliente vira um evento, com a execução, a skill ativa, a duração e o resultado. O Raio-X mostra isso ao vivo, e as gravações guardam tudo. Para uma decisão de impacto, a proveniência diz de onde veio cada dado usado.

### A skill não engessa o agente?

Não. A skill define o que **precisa** acontecer antes de quê (consentimento antes do imóvel, adequação antes da proposta, aprovação antes de emitir), não um roteiro de falas. Dentro disso, o agente conversa, pergunta, escolhe a seguradora com a cliente e se adapta: na cena 6, ele desvia da Âncora fora do ar sem nenhuma instrução específica para isso. Veja o [capítulo 3](03-skills-como-gps.md#a-ordem-tambem-e-lei).
