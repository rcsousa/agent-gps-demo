# Bastidores da demo GPS de Contexto

**Agentes que chegam mais longe, porque entendem o caminho.**

Este site explica o que acontece por trás de cada cena da demo do Banco Bússola. Cada capítulo começa com um **resumo executivo**, para quem quer a ideia em um minuto, e segue com o **aprofundamento técnico**, para quem quer ver as peças.

![Mapa da demo GPS de Contexto](assets/infografico.jpeg)

## Os capítulos

1. [O problema](01-o-problema.md): por que agentes sem contexto falham.
2. [A camada de contexto](02-camada-de-contexto.md): o mapa, o trânsito e as regras.
3. [Skills como GPS](03-skills-como-gps.md): como o agente aprende a ler o mapa.
4. [Bastidores de cada cena](04-bastidores-das-cenas.md): o que a plateia viu e o que aconteceu de verdade.
5. [Anatomia da jornada de seguro](05-anatomia-da-jornada.md): ontologia, skills e regras.
6. [Arquitetura](06-arquitetura.md): serviços, fluxo de eventos e provedores de LLM.
7. [Como reproduzir](07-como-reproduzir.md): subir a demo e rodar cada cena.
8. [Glossário e perguntas frequentes](08-glossario-e-faq.md).

!!! info "Estado atual: Fase 6 · Mapa"
    A demo abre no infográfico navegável e a viagem do agente aparece no Modo Mapa, uma cidade em 3D desenhada a partir do grafo, com o robô percorrendo a rota evento a evento. O mapa existe, o gateway reúne 41 tools, 4 skills e 3 prompts de 9 servidores MCP e aplica a governança por skill, inclusive a ordem do workflow, e o simulador muda o mundo de verdade. O agente dirige a jornada nos três modos (sem contexto, sem skill e com skill) e publica cada passo no barramento. A persona do agente vem do banco, por canal (app, agência e central). O dashboard de status mostra cada tool, skill e prompt por dentro, com contrato, código e uso. Os capítulos 1, 2, 3, 5, 6 e 7 descrevem o que já funciona, e o capítulo 8 já traz a tabela da metáfora; os outros ganham conteúdo nas próximas fases.
