# 7. Como reproduzir

!!! abstract "Resumo executivo"
    Você só precisa do Docker. Copie o arquivo de configuração, rode um comando e abra o navegador. Nada é instalado fora dos containers.

## Aprofundamento técnico

### Subir a demo

```bash
cp .env.example .env        # preencha as chaves se for usar um LLM de verdade
docker compose up -d --build
docker compose ps           # todos os serviços devem aparecer como "healthy"
```

| Endereço | O que é |
| --- | --- |
| <http://localhost:8080> | Tela de abertura: o infográfico navegável |
| <http://localhost:8080/mapa> | Modo Mapa: a cidade e a viagem do agente |
| <http://localhost:8080/status> | Dashboard de status |
| <http://localhost:8080/bastidores/> | Este site |
| <http://localhost:7474> | Neo4j Browser (usuário e senha do `.env`) |

### Rodar os testes

Os testes rodam dentro dos containers:

```bash
# Testes de um serviço
docker compose run --rm --no-deps agent pytest

# Todos os testes de unidade e o lint
./scripts/testar.sh

# Checagem ponta a ponta, com a demo no ar
docker compose --profile test run --rm --build smoke

# No navegador (Chromium): abertura, mapa, viagem e incidente. Usa o roteiro, sem tokens
docker compose --profile test run --rm --build e2e
```

### Atualizar dependências

Cada serviço Python tem um `uv.lock` versionado, e o build usa `uv sync --locked`. Na prática, duas máquinas instalam exatamente as mesmas versões. Se alguém mudar um `pyproject.toml` e esquecer o lock, o build falha logo, em vez de instalar versões diferentes sem aviso.

```bash
# Depois de mudar um pyproject.toml
./scripts/travar-dependencias.sh agent        # só o serviço alterado
./scripts/travar-dependencias.sh              # todos

# Para subir as versões dentro das faixas permitidas
./scripts/travar-dependencias.sh --upgrade
```

O script roda o `uv` dentro de um container, então não é preciso instalar nada na máquina.

### Chamar tools como o agente

Com a demo no ar, `gateway.sh` chama qualquer tool pelo MCP gateway, com o mesmo caminho e o mesmo token do agente. A resposta mostra o `_meta` com a proveniência:

```bash
./scripts/gateway.sh --listar                                  # as 41 tools
./scripts/gateway.sh cliente.obter_perfil '{"cliente_id": "cliente-ana"}'
./scripts/gateway.sh seguradoras.cotar_seguro '{"cliente_id": "cliente-ana", "seguradora": "farol"}'
./scripts/gateway.sh contexto.consultar_rota
./scripts/gateway.sh contexto://mapa
```

Para ver as chamadas no barramento:

```bash
docker compose exec bus redis-cli XREVRANGE bussola:eventos + - COUNT 5
```

No Neo4j Browser, a vizinhança da Ana:

```cypher
MATCH p=(:Cliente {id:'cliente-ana'})-[*1..2]-() RETURN p
```

### Mudar a ontologia

1. Edite os arquivos em `services/contexto-mcp/ontologia/`.
2. Se adicionou ou removeu entidades, recalcule o layout da cidade: `./scripts/gerar-layout.sh`.
3. Versione `ontologia/layout.json` junto. O seed se recusa a subir com layout desatualizado, e um teste também acusa.
4. `docker compose up -d --build`: o `seed` recarrega o grafo.

### Simular um serviço fora do ar

```bash
docker compose stop risco-mcp    # o tile "Risco" fica vermelho em até 5 s
docker compose start risco-mcp   # e volta ao verde
```

### Aplicar incidentes

`incidente.sh` é o painel do apresentador por linha de comando:

```bash
./scripts/incidente.sh listar
./scripts/incidente.sh aplicar cotacao-ancora-fora     # rua interditada
./scripts/gateway.sh contexto.consultar_rota            # a rota rápida aparece bloqueada
./scripts/incidente.sh remover cotacao-ancora-fora
./scripts/incidente.sh reset                           # tudo volta ao estado-base
```

No pedágio (`alcada-ana-excedida`), a proposta exige um especialista. Depois de `atendimento.solicitar_aprovacao`, decida com `./scripts/incidente.sh aprovar <ticket>` (ou `recusar`). Se ninguém decidir em 30 s, a especialista Marina aprova.

| Incidente | Metáfora |
| --- | --- |
| `cotacao-ancora-fora` | Rua interditada |
| `emissao-lenta` | Congestionamento |
| `consentimento-ana-expirado` | Contramão |
| `vistoria-zona-sul` | Desvio por obra |
| `alcada-ana-excedida` | Pedágio |
| `proveniencia-fraca-ana` | Ponte interditada |

### A tela de abertura

<http://localhost:8080> abre o infográfico da demo. Para aproximar, arraste e use a roda do mouse ou os botões `+` e `−`. Ao passar o mouse, cada área acende e mostra para onde leva:

- as mensagens 1, 2 e 3, a Ana, o celular, as rotas e as seguradoras levam à cena correspondente, já no mapa;
- as paradas 1 a 9 (no mapa ou na faixa) abrem o mapa perto daquela parada;
- a placa, a camada de contexto, a skill, a proveniência e a tabela da metáfora levam ao capítulo destes bastidores;
- o seletor Mapa / Raio-X e a área "Modo Raio-X: transparência total" abrem o Raio-X;
- as áreas de bastidores abrem o capítulo num painel ao lado, sem sair do infográfico.

**Atalhos:** `Enter` inicia a demo, `M` abre o mapa, `S` abre o status e `B` abre os bastidores. `Tab` percorre as áreas.

### O Modo Mapa

<http://localhost:8080/mapa> mostra a cidade do banco: ruas, avenidas, o rio com pontes e uma construção para cada lugar do grafo. São os 5 bairros do infográfico: casas, sobrados e a sede do banco em Cliente e Relacionamento; prédios públicos, a cúpula e escritórios em Regras e Governança; lojas, galerias e o shopping em Produtos e Ofertas; torres de vidro e prédios técnicos em Serviços e Parceiros; agências, o data center e cartórios em Pagamentos e Emissão. O trânsito é ao vivo.

![A cidade em grade, com uma construção por lugar do banco](assets/mapa/cidade.png)

**Navegar:**

- arraste para mover e use a roda para o zoom;
- para girar e inclinar, use o botão direito (ou Ctrl + arrastar) ou os botões de girar e inclinar, ao lado do zoom;
- a bússola mostra para onde o mapa aponta e, ao clicar, volta o norte para cima;
- "Enquadrar a cidade" volta à vista inicial;
- clique no nome de um bairro para ir até ele.

**De perto, aparecem os nomes das construções.** Clique em uma para ver os atributos, o estado vivo, a **proveniência** e os vizinhos.

![De perto, os nomes dos lugares de Parceiros: as APIs das seguradoras e os sistemas do banco](assets/mapa/bairro.png)

![O detalhe de um lugar, com a proveniência](assets/mapa/no.png)

**Fazer uma viagem:**

1. Na barra de viagem, escolha o **modo** (com skill, sem skill ou sem contexto), o **canal** e o **modelo**. A opção "Roteiro (ensaio sem LLM)" não gasta tokens.
2. Clique em **Iniciar viagem**. O endereço muda para `/mapa?execucao=<id>`, e dá para abrir o mesmo link em outra tela.
3. O robô sai da porta do canal e anda pelas ruas até cada lugar que o agente usa: o CRM, o cofre de consentimentos, o motor de risco, as APIs das seguradoras, o gateway de pagamentos… O caminho acende em laranja atrás dele, e as placas das paradas acendem quando ele passa. Com "Seguir o agente" ligado, a câmera de GPS fica baixa, atrás dele, e o mapa gira com o robô: a direção da viagem fica sempre para cima. Se você mexer na câmera, o seguimento pausa até religar.
4. **Passo a passo** (ligado por padrão, na barra): a cada sistema que o agente usa, o robô abre um balão de fala com o que está fazendo e espera. Clique em **Seguir**, ou aperte **Espaço**, para o balão sumir e a jornada continuar. O agente não espera: só o mapa. Desligado, a viagem corre sozinha.
5. Quando o agente perguntar algo à Ana, a pergunta aparece no painel **Conversa** assim que o robô chega à parada dela. Responda com um dos botões ou escreva a resposta.
6. No fim, a câmera sobe para a cidade inteira, com o caminho todo aceso, e fica livre para explorar.
7. O selo no alto mostra "Reproduzindo" enquanto o mapa está atrás do agente e "Ao vivo" quando alcança. **Pular para o fim** alcança de uma vez.

![A viagem com skill: o robô andando pelas ruas, com o caminho real aceso](assets/mapa/viagem.png)

![O passo a passo: o balão de fala do robô espera o apresentador mandar seguir](assets/mapa/balao.png)

**Cenas prontas.** `/mapa?cena=6` deixa a barra pronta para a cena 6 e mostra o botão **Derrubar a API da Âncora**. Inicie a viagem e, na primeira pergunta do agente à Ana, derrube a API: o farol vermelho sobe do prédio dela. Na cotação, o agente percebe a rua interditada, recalcula citando a regra e segue com as outras seguradoras. Se a API cair antes da viagem, ele já planeja sem a Âncora, e não há recálculo para mostrar.

![A cena 6: o farol da Âncora](assets/mapa/incidente.png)

Depois, volte o mundo ao normal com `./scripts/incidente.sh reset`.

### O Modo Raio-X

O seletor **Mapa / Raio-X**, na barra do mapa, troca a apresentação sem reiniciar a viagem: é a mesma execução, vista por dentro. O endereço ganha `?visao=raio-x`.

![O Modo Raio-X: o log de chamadas MCP ao lado da cidade como grafo](assets/raio-x/chamadas.png)

- **No mapa**, aparecem as relações do grafo como arcos entre as construções e, fora do GPS, os nomes de todas elas.
- **Chamadas MCP:** cada `tools/list`, `skills/list`, `resources/read`, `prompts/get`, chamada de tool, passo do modelo e decisão de rota, na ordem em que aconteceram, com duração e status. Bloqueios do gateway aparecem com cadeado. Clique numa linha para ver o evento cru do barramento.
- **Conversa:** a mesma do Modo Mapa. Quando o agente pergunta algo, as opções da Ana aparecem no topo do painel, em qualquer aba.
- **Proveniência:** as decisões do agente (rota, recálculo e incidente), com motivo e regra, e os sistemas e dados que ele tocou. Clique num deles para ver fonte, data, responsável e confiança.
- **Métricas:** tokens (com o que veio do cache), tempo no modelo e nas tools, custo, as regras do banco conferidas no fim e as tabelas por passo do modelo e por tool.
- **Placar:** a última viagem de cada modo nesta sessão, o agregado por modo × modelo e a referência do experimento Opus × Haiku.

![O placar: a sessão e a referência com os modelos reais](assets/raio-x/placar.png)

### O painel do apresentador

No mapa, a tecla **P** (ou o botão **Apresentador**) abre a gaveta do apresentador:

- **Cenas 1 a 8**, com o tempo-alvo e o filtro "versão curta" (1, 4, 5, 6 e 8). **Ao vivo** limpa o mundo e prepara o mapa para a cena; a viagem começa no **Iniciar viagem**. **Replay** toca a gravação da cena. A cena 8 abre o Raio-X na última viagem com skill.
- **Bastidores** (ícone de livro) abre o capítulo da cena num painel ao lado. Na barra do mapa, o mesmo atalho aparece como **Bastidores da cena**.
- **Falas da Ana**, nas cenas 3 e 7: a do estorno e a da coleção de arte. Elas são enviadas como resposta quando o agente pergunta algo.
- **Pedágio:** as aprovações pendentes, com aprovar e recusar e a contagem até a especialista Marina aprovar sozinha (30 s).
- **Incidentes:** cada um com liga/desliga; o da cena atual aparece em destaque. Na cena 6, derrube a Âncora **durante** a viagem, para o recálculo acontecer ao vivo.
- **Tools desligadas** e **Mundo limpo**, que volta tudo ao estado-base.

![A gaveta do apresentador](assets/raio-x/apresentador.png)

### Regerar os vídeos e as capturas dos bastidores

Os vídeos do capítulo 4 são os replays reais, acelerados. Depois de mudar o visual, regere sem gastar tokens (com a demo no ar):

```bash
./scripts/capturar-cenas.sh          # todas as cenas
./scripts/capturar-cenas.sh 6 7      # só algumas
```

### Gravar e tocar (replay offline)

- No fim de uma viagem ao vivo, **Gravar esta viagem** salva a execução em `gravacoes/cena-<n>.jsonl` (ou com o id da execução, fora de uma cena). Grave de novo para substituir.
- `/mapa?gravacao=cena-6`, ou o botão **Replay** da gaveta, toca a gravação: sem rede, sem chave e sem LLM. O selo "Replay" fica visível o tempo todo.
- As gravações versionadas foram feitas com o Haiku de verdade. As cenas 4 e 8 usam a gravação da cena 5, que é a mesma viagem.
- Para regravar todas as cenas com o modelo do `.env` (gasta tokens, cerca de US$ 0,06 com o Haiku), use o roteiro de gravação descrito no capítulo 4.

### O dashboard de status

Em <http://localhost:8080/status> fica o console de quem monta e apresenta a demo:

- no topo, os indicadores: serviços no ar, tools (e quantas estão fora do ar), skills, prompts, o provedor de LLM e o barramento;
- abaixo, as abas **Serviços**, **Tools**, **Skills** e **Prompts**, cada uma com busca. Na aba Tools, há também um filtro por servidor.

Clique numa linha para abrir o **painel lateral**, que mostra o item por dentro:

| Item | O que o painel mostra |
| --- | --- |
| Tool | Descrição, servidor, as skills que a permitem, o **contrato** (parâmetros e JSON Schema), o **código Python real** com arquivo e linha, e as **últimas chamadas** no barramento |
| Skill | Frontmatter e governança, o `SKILL.md` renderizado, os arquivos de referência com digest verificado e o uso recente |
| Prompt | Canal, interlocutor e argumentos, a **prévia** renderizada para a Ana e o `.md` de origem |
| Servidor | Status, latência e tudo o que ele oferece, incluindo o que fica oculto |

![Uma tool no painel lateral: visão geral](assets/dashboard/tool-visao-geral.png)

![O código da tool, servido pelo próprio servidor MCP](assets/dashboard/tool-codigo.png)

![As últimas chamadas da tool no barramento](assets/dashboard/tool-chamadas.png)

A URL acompanha a navegação. Por exemplo, `/status/tools/seguradoras.cotar_seguro` abre direto o painel dessa tool: dá para mandar o link para alguém.

### Desligar uma tool

Além dos incidentes, dá para criar falhas sob medida, tool a tool. Na aba **Tools** do dashboard, o toggle de cada linha (ou do painel da tool) desliga ou religa a tool, e **"Religar todas"** volta tudo ao normal. O indicador do topo mostra quantas estão fora.

Uma tool desligada **continua visível** para o agente, mas toda chamada falha com "trecho interditado". É a falha que o agente precisa perceber e contornar. O controle passa pelo simulador, pelo caminho `/simulador` do web; o agente não o alcança.

Pela linha de comando:

```bash
./scripts/incidente.sh desligar seguradoras.cotar_seguro
./scripts/incidente.sh tools                       # o que está fora do ar
./scripts/incidente.sh religar seguradoras.cotar_seguro
```

`incidente.sh reset` também religa todas as tools.

### Criar um novo incidente

Acrescente uma entrada em `services/simulator/incidentes.yaml`. Cada efeito aponta para uma entidade da ontologia, pelo id, e muda:

- `estado`: `status`, `latencia_ms`, `custo_estimado`, `vigencia_fim`;
- `atributos` ou `proveniencia`;
- relações (`relacoes_adicionar`).

Datas podem ser relativas (`$hoje`, `$ontem`). Depois de `docker compose up -d --build simulator`, o incidente aparece em `incidente.sh listar`. O smoke aplica todos os incidentes do catálogo ao mapa real, para garantir que nenhum aponta para entidade inexistente.

### Escrever uma nova skill

1. Crie `services/skills-mcp/skills/<nome>/SKILL.md`. O frontmatter precisa de `name` igual ao nome da pasta, de `description` (o que a skill faz e quando usar) e de `allowed-tools` com os nomes qualificados do gateway (`cliente.obter_perfil`...).
2. Se reutilizar outras skills, liste-as em `metadata.usa-skills` e aponte para elas pela URI (`skill://<nome>/SKILL.md`).
3. Coloque os trechos longos em `references/*.md` e cite cada um pela URI completa no `SKILL.md`.
4. `docker compose up -d --build skills-mcp`. Em até 30 s o gateway relê o catálogo, e `./scripts/gateway.sh --skills` mostra a skill nova.

Os testes recusam:

- skill com `name` diferente da pasta;
- tool fora do formato `prefixo.tool`;
- `usa-skills` que não existe;
- arquivo de apoio citado e ausente, ou presente e não citado.

O smoke confere que toda tool permitida existe no gateway.

Para testar a governança: `./scripts/gateway.sh <tool> '{...}' --skill <nome>`. Com skill, a ordem vale por execução: o script gera um id e mostra como repeti-lo com `--execucao <id>`, para encadear chamadas.

### Declarar a ordem de uma skill

Crie `workflow.yaml` na pasta da skill e cite-o no `SKILL.md` (`skill://<nome>/workflow.yaml`). Duas seções:

- `pre-requisitos`: para cada tool, a lista do que precisa ter dado certo antes, na mesma execução. Cada item é uma tool (`risco.consultar_elegibilidade`), uma tool com campos do resultado (`consentimento.verificar: { permitido: true }`) ou `qualquer:` com alternativas;
- `impedimentos`: tools que ficam bloqueadas depois que outra aconteceu.

Os testes do `skills-mcp` recusam um workflow mal formado ou que cite tools que a skill não permite.

### Dirigir o agente

`agente.sh` inicia uma execução e mostra a viagem no terminal, evento a evento. Sem chave de API, use o provedor `roteiro`:

```bash
./scripts/agente.sh executar --modo com_skill --provedor roteiro
```

Quando o agente pergunta algo à Ana, a execução pausa e o terminal mostra as opções sugeridas. Responda de outro terminal:

```bash
./scripts/agente.sh responder <id> --sugestao 1               # a primeira opção sugerida
./scripts/agente.sh responder <id> "Sim, é esse apartamento"  # texto livre
./scripts/agente.sh estado <id>                               # status, pergunta pendente e métricas
```

Para ensaiar sem apresentador, `--auto` responde sempre com a primeira opção. Os três modos:

```bash
./scripts/agente.sh executar --modo sem_contexto --provedor roteiro --auto   # zero tools, resposta inventada
./scripts/agente.sh executar --modo sem_skill    --provedor roteiro --auto   # tools irrelevantes
./scripts/agente.sh executar --modo com_skill    --provedor roteiro --auto   # as 9 paradas até a apólice
```

Com um incidente aplicado antes ou durante a viagem, o agente percebe e recalcula:

```bash
./scripts/incidente.sh aplicar cotacao-ancora-fora
./scripts/agente.sh executar --modo com_skill --provedor roteiro --auto
#   ⚠ incidente: Rua interditada · A API de cotação da Âncora Seguros está fora do ar...
# ◆ rota recalculada: rota-rapida → rota-economica · ...
```

O canal escolhe a persona: `--canal app` (padrão), `agencia` ou `central`. O modelo padrão é o Haiku 5.5. Para trocar o modelo de todas as próximas execuções, use o seletor no indicador de LLM do dashboard, ou `curl -X PUT localhost:8080/api/llm/modelo -H 'Content-Type: application/json' -d '{"modelo": "claude-opus-5-5"}'`. Para uma execução só, `--modelo claude-opus-5-5`. O fim da viagem mostra o custo em US$.

```bash
./scripts/agente.sh executar --modo com_skill --provedor roteiro --canal agencia --auto
# ◆ persona do canal: canais.atendimento_agencia (pelo gateway)
#   ? pergunta: Confirme com a Ana: o seguro é para o apartamento dela na Vila Mariana, em São Paulo?
```

Com o modelo configurado no `.env` (por padrão, o Claude no Microsoft Foundry: `ANTHROPIC_FOUNDRY_BASE_URL` e `ANTHROPIC_FOUNDRY_API_KEY`; veja o capítulo 6), rode sem `--provedor`: vale o `LLM_PROVIDER`. O indicador de LLM do dashboard mostra o modelo, a plataforma e se a chave está configurada. Depois de mudar o `.env`, recrie o agente com `docker compose up -d agent`.

Pela API, o mesmo caminho que o painel do apresentador vai usar:

```bash
curl -s -X POST localhost:8080/api/execucoes -H 'Content-Type: application/json' \
  -d '{"modo": "com_skill", "provedor": "roteiro"}'
curl -N localhost:8080/api/execucoes/<id>/eventos          # SSE
curl -s -X POST localhost:8080/api/execucoes/<id>/resposta -H 'Content-Type: application/json' \
  -d '{"texto": "Aceito"}'
```

### Ensaiar a apresentação

`./scripts/ensaiar.sh` é o ensaio de palco. **Não gasta tokens.**

1. Derruba a demo, sobe de novo e mede o tempo até tudo ficar saudável.
2. Toca as 8 cenas no navegador, em 1920 × 1080, pelo roteiro:
   - no passo a passo, com Espaço em cada balão;
   - a Ana responde pela primeira opção;
   - na cena 6, a API da Âncora cai na primeira pergunta à Ana;
   - na cena 7, o pedágio é aprovado no painel do apresentador.
3. Toca os replays das gravações.
4. Escreve `ensaios/<data>.md`, com os critérios de aceite (✔/✘ e a evidência) e as capturas de cada cena.

```bash
./scripts/ensaiar.sh            # com a subida a frio
./scripts/ensaiar.sh --quente   # com a demo já no ar
```

O roteiro de fala e o checklist do dia estão no capítulo 9.

### Medir com o modelo real

`experimento.sh` roda cada incidente nos modos `sem_skill` e `com_skill`, com o modelo do `.env`, e confere pelo barramento se o agente seguiu a regra do banco. **Gasta tokens de verdade.**

```bash
./scripts/experimento.sh rodar                       # o caminho feliz e os 6 incidentes x 2 modos (~12 min)
./scripts/experimento.sh rodar vistoria-zona-sul     # só um incidente
./scripts/experimento.sh analisar 2026-11-01-claude-opus-5-5   # regras por caso, somando as repetições

# Comparar modelos: cada execução pode pedir um modelo de ANTHROPIC_MODELOS
./scripts/experimento.sh rodar --modelo claude-haiku-5-5 --repeticoes 3
./scripts/experimento.sh comparar 2026-11-01-claude-opus-5-5 2026-11-01-claude-haiku-5-5
```

O `comparar` mostra também o custo, pelos preços do `.env`. Mudar os preços ou os fatores de cache e comparar de novo não gasta tokens: o custo é recalculado a partir dos tokens gravados.

Os eventos completos ficam em `experimentos/<data>/`, fora do git. Os relatórios ficam em `docs/experimentos/`; o mais recente cobre os 6 incidentes com o Haiku.

### Escrever a persona de um canal novo

As personas são prompts MCP servidos pelo `canais-mcp`, um arquivo por canal:

```bash
./scripts/gateway.sh --prompts                                                   # as personas
./scripts/gateway.sh --prompt canais.atendimento_central '{"cliente_id": "cliente-ana"}'
```

1. Crie `services/canais-mcp/prompts/<canal>.md`. O frontmatter precisa de:
    - `name`, igual a `atendimento_<canal>`;
    - `canal`, o id de um `Canal` da ontologia (por exemplo, `canal-internet-banking`);
    - `title` e `description`;
    - `interlocutor`: com quem o agente fala nesse canal.
2. Escreva a persona em pt-BR: quem é o agente, com quem fala, o tom e o que pode prometer. Use `{cliente_nome}` e `{cliente_id}`, que o servidor preenche com o cadastro. Deixe de fora as regras de negócio: elas são da skill.
3. `docker compose up -d --build canais-mcp`. Em até 30 s o gateway relê o catálogo, e o canal passa a valer em `--canal <canal>`.

Os testes recusam um frontmatter incompleto ou um `name` fora do padrão. O smoke confere que o canal de cada persona existe na ontologia.

Para ver o fallback, pare o servidor: `docker compose stop canais-mcp`. A execução segue com a persona embutida, e o terminal mostra `◆ persona embutida` com o motivo. Depois, `docker compose start canais-mcp`.
