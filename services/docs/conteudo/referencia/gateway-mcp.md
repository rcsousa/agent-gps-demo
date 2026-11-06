# O padrão do gateway MCP

!!! abstract "Resumo"
    O agente conhece **um** endereço: o `mcp-gateway`. Para ele, o gateway é um servidor MCP como outro qualquer. Por trás, o gateway é cliente MCP de cada servidor de negócio. Ele junta as tools, os prompts, os resources e as skills de todos num catálogo só, com nomes qualificados, e aplica a governança **em cada chamada**: quem pode chamar, o que a skill ativa permite, em que ordem, de onde veio cada dado e o que fica registrado. A regra do banco deixa de depender de o modelo obedecer.

## A forma

![O padrão do gateway: o agente fala com um servidor MCP, e o gateway fala com todos os outros](../assets/diagramas/gateway.svg)

--8<-- "numeros-gateway.md"

## O que o agente vê

- **Um transporte e um endereço:** Streamable HTTP em `http://mcp-gateway:8000/mcp`, com `Authorization: Bearer <GATEWAY_TOKEN>`. Sem o token, o gateway responde 401 antes de qualquer MCP.
- **O protocolo padrão:**
  - `initialize`;
  - `tools/list` e `tools/call`;
  - `prompts/list` e `prompts/get`;
  - `resources/list` e `resources/read`;
  - a extensão de skills `io.modelcontextprotocol/skills` (SEP-2640), com `skills/list` e `skills/get`.
- **Nomes qualificados:** cada tool aparece como `<prefixo>.<tool>` (`cliente.obter_perfil`, `seguradoras.cotar_seguro`), e a descrição começa com o prefixo. Dois servidores podem ter tools com o mesmo nome sem colidir, e o agente sabe de que domínio cada uma é.
- **Nenhuma URL de serviço de negócio no agente:** a configuração do `agent` tem só o `GATEWAY_URL`, o `GATEWAY_TOKEN` e o barramento.

**O agente também executa algumas tools por conta própria,** as tools do host. Elas não tocam nenhum sistema do banco:
- leem a skill (pelo gateway, com o digest conferido);
- narram a viagem para o mapa;
- perguntam à cliente.

--8<-- "tools-do-host.md"

## A agregação

A cada ciclo, o gateway lista cada upstream do `upstreams.yaml` e monta o catálogo.

- **Um servidor fora do ar mantém o que já se sabia dele:** no mapa, a rua continua lá, interditada, em vez de sumir.
- **As skills e os workflows** (`workflow.yaml`) vêm do `skills-mcp` pela mesma extensão que o agente usa.

```python
--8<-- "gateway/catalogo.py:agregacao"
```

## A governança em cada chamada

Toda `tools/call` passa pelo mesmo caminho.

**Antes de chamar o servidor:**
1. **Contramão por skill:** com uma skill ativa (`_meta["bussola/skill"]`), só valem as `allowed-tools` dela.
2. **Contramão por ordem:** os pré-requisitos do `workflow.yaml` são conferidos contra os **fatos desta execução** (`_meta["bussola/execucao"]`), como "consentimento verificado com `permitido: true`".

**Depois da resposta:**
3. **A proveniência é carimbada** no resultado: a chamada, a tool, o servidor, a skill, a execução, o instante, a duração e o status.
4. **O fato da execução é registrado.** O que deu certo vira fato, e é isso que os pré-requisitos das próximas chamadas consultam.
5. **O evento `tool.called` é publicado** com os argumentos e um resumo do resultado. É dele que o Raio-X e o placar se alimentam.

```python
--8<-- "gateway/servidor_mcp.py:governanca"
```

```python
--8<-- "gateway/servidor_mcp.py:chamada"
```

**A contramão nunca chega ao servidor de negócio.** O agente recebe um erro que diz o que falta, como "Contramão: `seguradoras.cotar_seguro` exige antes: `risco.consultar_elegibilidade`", e o mapa mostra o bloqueio em vermelho. A ordem da skill de contratação está desenhada no capítulo 3, em "A ordem também é lei".

## As sequências, de execuções reais

Os dois trechos abaixo são gerados das gravações das cenas 6 e 7.

**Rua interditada:** a API de cotação da Âncora cai. O agente percebe na consulta e recalcula a rota citando a regra da skill.

![Sequência do recálculo: incidente percebido numa tool, recálculo e as próximas chamadas](../assets/diagramas/sequencia-recalculo.svg)

**Pedágio:** o valor passa da alçada. O agente pede a aprovação de um especialista e acompanha o ticket, sempre pelo gateway.

![Sequência do pedágio: aprovação humana pedida e acompanhada pelo gateway](../assets/diagramas/sequencia-pedagio.svg)

## Por que o padrão importa

| Propriedade | Com o gateway | Com o agente ligado direto a N servidores |
| --- | --- | --- |
| **Superfície de ataque** | O agente tem um endereço e um token. Os servidores de negócio nem são alcançáveis pelo agente fora do gateway. | O agente guarda N URLs e N credenciais. Um prompt injetado pode tentar qualquer uma. |
| **Política** | Aplicada num ponto só, fora do modelo: skill, ordem e alçada. Vale igual para qualquer modelo e qualquer provedor. | Cada servidor teria de reimplementar a política, ou ela ficaria no prompt, e o modelo pode não obedecer. |
| **Auditoria e proveniência** | Toda chamada vira um evento com a mesma forma, com quem, o quê, quando, de onde e quanto tempo levou. | Cada servidor loga do seu jeito, e juntar a história de uma execução vira um projeto. |
| **Evolução dos backends** | Trocar, dividir ou desligar um servidor é editar o `upstreams.yaml`. O agente não muda. | Cada mudança de backend é uma mudança no agente. |
| **Descoberta** | Tools, prompts, resources e skills chegam por um catálogo só, com nomes sem colisão. | O agente precisa juntar N catálogos e resolver as colisões. |
| **Resiliência** | Um servidor fora vira "trecho interditado", com uma mensagem que o modelo entende e a skill sabe tratar. | Um timeout diferente para cada servidor. |
| **Credenciais** | As do banco ficam nos servidores. A do modelo, só no agente. | O agente acumula as credenciais de todos os sistemas. |

**O efeito medido:**
- **Sem skill,** o agente com contexto cumpre algumas das regras do banco.
- **Com skill e com o gateway impondo ordem e permissões,** ele cumpre praticamente todas, inclusive com um modelo menor.

Os números estão no capítulo 1.

## Fontes no repositório

| O quê | Onde |
| --- | --- |
| Os upstreams | `services/mcp-gateway/config/upstreams.yaml` |
| Agregação e nomes qualificados | `services/mcp-gateway/src/mcp_gateway/catalogo.py` |
| Servidor MCP, governança e eventos | `services/mcp-gateway/src/mcp_gateway/servidor_mcp.py` |
| Token | `services/mcp-gateway/src/mcp_gateway/main.py` |
| Tools do host | `services/agent/src/agent/ferramentas.py` |
| Catálogo versionado | `services/smoke/referencia/catalogo.json` (`./scripts/gerar-referencia.sh`) |
