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

!!! tip "Comece por aqui"
    - **Viu uma cena e quer entender?** O [capítulo 4](04-bastidores-das-cenas.md) tem cada cena: o vídeo, o que aconteceu de verdade e as regras conferidas.
    - **Executivo, cinco minutos?** Leia só os resumos dos capítulos [1](01-o-problema.md), [2](02-camada-de-contexto.md) e [3](03-skills-como-gps.md).
    - **Técnico, desconfiado?** Vá ao [capítulo 8](08-glossario-e-faq.md): as objeções mais comuns, com resposta curta e o caminho até o código.
    - **Quer rodar?** O [capítulo 7](07-como-reproduzir.md) sobe a demo com um comando.

!!! info "Estado atual: Fase 8 · Bastidores"
    A demo abre no infográfico navegável. A viagem do agente aparece no Modo Mapa (a cidade em 3D) e no Modo Raio-X (o protocolo, a proveniência, as métricas e o placar). O apresentador conduz as cenas por uma gaveta no mapa (tecla P), e cada cena com viagem tem uma gravação real com o Haiku, para o replay sem rede. O botão "Bastidores" de cada cena abre o capítulo ao lado, sem sair da demo. Os diagramas e os trechos de código destes capítulos são gerados do próprio repositório.
