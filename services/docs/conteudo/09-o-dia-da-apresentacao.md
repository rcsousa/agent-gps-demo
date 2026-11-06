# 9. O dia da apresentação

!!! abstract "Resumo executivo"
    O roteiro de fala cena a cena (o que dizer, o que clicar e quanto tempo leva) e o checklist do dia: a véspera, os 30 minutos antes, os atalhos e os planos B e C. A demo inteira leva cerca de 13 minutos, com a abertura; a versão curta (abertura e cenas 1, 4, 5, 6 e 8), cerca de 9. Para imprimir, use o comando de impressão do navegador: cada cena sai numa página.

## Aprofundamento técnico

### Antes de começar

- **Modo telão:** tecla **T** (ou o painel do apresentador). A interface inteira cresce 25%, para ser lida a 5 m num Full HD.
- **Pausas:** "Só quando precisa de você" (padrão) faz a viagem fluir com os anúncios do GPS e parar só na pergunta à Ana e no pedágio. Para comentar cada passo, troque para **Passo a passo**: o robô para em cada anúncio e espera **Espaço**.
- **Voz do GPS:** ligue na barra para o GPS falar os anúncios. Teste o som antes, porque a voz é a do sistema da máquina.
- **Painel do apresentador:** tecla **P**. Nele ficam as cenas, os incidentes, o pedágio e as falas da Ana.
- **Atalhos:** tecla **?** mostra todos.

| Tecla | O que faz |
| --- | --- |
| `Enter` | Na abertura: inicia a demo |
| `I` | Na abertura: recolhe e mostra o painel sobre a demo |
| `P` | Abre e fecha o painel do apresentador |
| `Espaço` / `Enter` / `→` | Segue com a jornada quando o robô espera num balão |
| `T` | Liga e desliga o modo telão |
| `Esc` | Fecha painéis e janelas |
| `?` | Mostra os atalhos |

### Roteiro de fala, cena a cena { .roteiro }

#### Abertura · 1 min { .cena-impressa }

**Mostre:** a abertura, com o painel à esquerda e o infográfico à direita.

**Diga:** "Um agente de IA vai contratar um seguro residencial para a Ana. Para isso, ele precisa de um mapa, que é a camada de contexto, e de um GPS, que são as skills. Medimos com os modelos reais: com skill, o modelo menor cumpre 99% das regras do banco, contra 59% sem ela, e custa US$ 12 a cada mil contratações, 44 vezes menos que o maior. Vamos ver por quê."

**Clique:** **I** recolhe o painel, se quiser o infográfico inteiro para apontar as cenas.

#### Cena 1 · A cidade · 1 min { .cena-impressa }

**Clique:** na abertura, a área "Modo Mapa" (ou `Enter`). No painel, cena 1.

**Diga:** "Este é o banco visto como uma cidade. Cada prédio é algo que existe de verdade: um cliente, uma regra, uma API de seguradora. As cores são os bairros, os mesmos do infográfico. E o trânsito é ao vivo: se um sistema cai, a cidade mostra."

**Pergunta provável:** "Esse mapa é desenhado à mão?" **Resposta:** "Não. Ele é gerado do grafo de conhecimento do banco. Se a ontologia muda, o mapa muda junto."

#### Cena 2 · Dirigir sem mapa · 1,5 min { .cena-impressa }

**Clique:** cena 2 no painel (modo sem contexto) e **Iniciar viagem**. Responda pela Ana com as opções sugeridas.

**Diga:** "Agora o mesmo agente, com o mesmo modelo, mas sem a camada de contexto. Ele conversa bem, mas não tem como consultar nada: nem o cadastro, nem o consentimento, nem as seguradoras. Repare que o robô nem sai do lugar."

**Pergunta provável:** "Um modelo melhor não resolveria?" **Resposta:** "Não. Sem o mapa, até o modelo maior adivinha ou para. O experimento com o Opus está no capítulo 1."

#### Cena 3 · Mapa sem GPS · 1,5 min { .cena-impressa }

**Clique:** cena 3 (sem skill) e **Iniciar viagem**. Na conversa, use a fala da Ana no painel: "aproveita e estorna aquele pagamento duplicado".

**Diga:** "Aqui o agente tem todas as ferramentas, mas nenhum procedimento. Ele chega à apólice, mas puxa o dossiê completo da cliente e lê o imóvel sem conferir o consentimento. E, quando a Ana pede um estorno, nada o impede de tentar."

**Pergunta provável:** "Mas ele não fez a coisa certa?" **Resposta:** "Fez quase tudo. A questão é a garantia: sem a skill, nada impede o erro. Com ela, o gateway barra o que está fora da rota."

#### Cena 4 · Digitar o destino · 1,5 min { .cena-impressa }

**Clique:** cena 4 (abre o Raio-X da viagem com skill). Aponte o log: `skills/list`, a leitura do `SKILL.md` e a consulta das rotas.

**Diga:** "Com skill, a primeira coisa que o agente faz é perguntar quais procedimentos existem e ler o que serve para este pedido. A skill é a porta de entrada: ela diz quais ferramentas usar, em que ordem e o que fazer se algo mudar."

**Pergunta provável:** "Isso é um padrão?" **Resposta:** "É a extensão de skills do MCP (SEP-2640). Qualquer agente que fale MCP descobre e lê a skill do mesmo jeito."

#### Cena 5 · A viagem · 2 min { .cena-impressa }

**Clique:** cena 5 e **Iniciar viagem**. A cada balão, diga o que ele mostra e aperte **Espaço**.

**Diga:** "Agora o robô navega. A câmera vai atrás dele, como um GPS. Cada parada da linha do tempo acende, e cada balão é uma chamada real: o CRM, o cofre de consentimentos, o motor de risco, a seguradora. Quando ele precisa da Ana, pergunta, e a apólice só sai na emissão."

**Pergunta provável:** "Isso é animação?" **Resposta:** "Cada movimento é um evento real do agente. O mapa só espera você mandar seguir; o agente não."

#### Cena 6 · Incidente · 2 min { .cena-impressa }

**Clique:** cena 6 e **Iniciar viagem**. Quando o agente fizer a primeira pergunta à Ana, **antes de responder**, clique em **Derrubar a API da Âncora**. Depois, responda.

!!! warning "Derrube a API com a viagem em curso"
    Se a API cair antes de a viagem começar, o agente já planeja a rota sem a Âncora, e a plateia não vê o recálculo. Com a viagem em curso, ele percebe a interdição na cotação e recalcula ao vivo, citando a regra.

**Diga:** "Vou derrubar a API de uma seguradora. Repare no farol vermelho subindo do prédio dela. O agente percebe a rua interditada, recalcula com a regra do banco, segue com as outras seguradoras e explica a troca para a Ana."

**Pergunta provável:** "E se cair no meio da contratação?" **Resposta:** "A skill tem o desvio para cada incidente: rua interditada, congestionamento, contramão e pedágio. O placar confere se ele foi seguido."

#### Cena 7 · Pedágio · 1 min { .cena-impressa }

**Clique:** cena 7 e **Iniciar viagem**. Use a fala da Ana sobre a coleção de arte. Quando o pedágio aparecer, aprove no painel (ou espere 30 s: a Marina aprova sozinha).

**Diga:** "O valor passou do limite de alçada automática. O agente para e chama um especialista humano. Nada é pago nem emitido sem a aprovação. Governança faz parte do mapa."

#### Cena 8 · Raio-X · 1,5 min { .cena-impressa }

**Clique:** troque para **Raio-X**: Chamadas MCP, Proveniência, Métricas e Placar.

**Diga:** "Por dentro, é tudo auditável: cada chamada, de onde veio cada informação e quanto custou. O placar compara as viagens de hoje: sem contexto, sem skill e com skill, em regras do banco cumpridas."

**Pergunta provável:** "Quanto custa?" **Resposta:** "Uma viagem com skill no Haiku custa cerca de um centavo de dólar. O placar mostra o custo de cada uma."

### Checklist do dia

**Na véspera:**

- [ ] `.env` com a chave do modelo (Foundry ou Anthropic) e o modelo da apresentação.
- [ ] `docker compose up -d --build` e `./scripts/ensaiar.sh`: o relatório em `ensaios/<data>.md` todo ✔.
- [ ] Uma viagem de verdade com o modelo do dia, para aquecer o cache.
- [ ] No notebook do dia: `/mapa?fps=1` durante uma viagem, com 50 quadros/s ou mais.

**30 minutos antes:**

- [ ] `docker compose up -d` e o status (`/status`) todo verde.
- [ ] Uma viagem pelo roteiro (ensaio sem LLM), para aquecer o navegador.
- [ ] Mundo limpo: **Mundo limpo** no painel do apresentador (ou `./scripts/incidente.sh reset`).
- [ ] Modo telão (**T**) ligado, as pausas escolhidas e, se for usar, a voz do GPS testada no som da sala; o navegador em tela cheia (`F11`).

**Se algo der errado:**

- **O modelo demorou ou travou:** **Pular para o fim**. Se ainda assim não andar, toque a cena em **replay**, pelo painel do apresentador.
- **Sem rede (plano B):** os replays tocam sem rede e sem chave, com o selo "Replay" visível. É honesto: a gravação é de uma viagem real.
- **O navegador não ajuda (plano C):** os vídeos de cada cena estão no capítulo 4 destes bastidores.
- **Um incidente ficou ligado:** **Mundo limpo** no painel.
