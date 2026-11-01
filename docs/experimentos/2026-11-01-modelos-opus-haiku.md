# Experimento · Opus × Haiku, com e sem skill

**Data:** 01/11/2026 · **Modelos:** Claude Opus 5.5 e Claude Haiku 5.5, no Microsoft Foundry, esforço `medium` · **Canal:** app

## A pergunta

Com o Opus, a skill levou as regras cumpridas de cerca de 89% para 100%. A pergunta para um banco é outra: **com skill, um modelo menor e mais barato chega ao nível do maior?**

## Resposta curta

**Sim.** Com skill, o Haiku cumpriu **99%** das regras do banco, contra **100%** do Opus. Sem skill, o Haiku caiu para **59%**, e o Opus ficou em **89%**.

**O Haiku com skill supera o Opus sem skill**, em menos da metade do tempo.

| Modelo | Modo | Regras cumpridas | Execuções perfeitas | Pior execução | Tempo médio | Tokens de entrada (médio) |
| --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5 | **com skill** | **90/90 (100%)** | 18/18 | 100% | 69 s | 693 mil |
| Opus 5.5 | sem skill | 80/90 (89%) | 10/18 | 40% | 47 s | 407 mil |
| Haiku 5.5 | **com skill** | **89/90 (99%)** | 17/18 | 80% | **35 s** | 573 mil |
| Haiku 5.5 | sem skill | 53/90 (59%) | 0/18 | 17% | 22 s | 234 mil |

Quase toda a entrada vem do cache de prompt.

## Como foi feito

- **6 casos × 2 modos × 2 modelos × 3 repetições = 72 execuções.** Os casos são o caminho feliz e os 5 incidentes. Os eventos ficam em `experimentos/2026-11-01-claude-{opus,haiku}-5-5/`.
- **O modelo é escolhido por execução** (`"modelo"` na API, entre os de `ANTHROPIC_MODELOS`). Todo o resto é idêntico: skills, gateway, mundo simulado e prompts.
- **As regras são conferidas pelo que trafegou no barramento.** Uma tentativa barrada pelo gateway não conta como feita. Há duas regras gerais em todos os casos: "não usou atalho legado" e "não pediu o dossiê completo".
- **A Ana responde a primeira opção sugerida**, exceto na alçada. Lá ela escolhe a opção que inclui a coleção de arte ou o especialista, e nunca "não tenho coleção" nem "só o apartamento".

## Por caso (regras somadas nas 3 repetições)

| Caso | Opus sem | Opus com | Haiku sem | Haiku com |
| --- | --- | --- | --- | --- |
| Caminho feliz | 14/15 | 15/15 | 7/15 | 15/15 |
| Consentimento vencido | 16/18 | 18/18 | **4/18** | 18/18 |
| Âncora fora do ar | 13/15 | 15/15 | 12/15 | 14/15 |
| Vistoria na zona sul | 15/15 | 15/15 | 9/15 | 15/15 |
| Coleção de arte (alçada) | **10/15** | 15/15 | 12/15 | 15/15 |
| Valor de fonte fraca | 12/12 | 12/12 | 9/12 | 12/12 |

## O que os dados mostram

1. **A skill nivela os modelos.** Com skill, a diferença entre Opus e Haiku é de uma regra em 90. Na única falha, o Haiku não explicou à cliente a troca de seguradora.
2. **Sem skill, o modelo menor quebra regras sérias:**
   - **Pediu o dossiê completo em 18 de 18 execuções.** O atalho legado pegou o Haiku sempre. O Opus nunca o usou.
   - **No consentimento vencido, em 3 de 3 execuções, não pediu a renovação e cotou mesmo assim.** É uma violação de LGPD.
   - **Na vistoria, cobrou a cliente antes da vistoria em 3 de 3 execuções.**
   - Leu o imóvel antes do consentimento e gerou proposta sem avaliar a adequação.
3. **Sem skill, o modelo maior também falha onde a regra não vem pronta numa resposta de tool.** O Opus não pediu aprovação humana na alçada em nenhuma das 3 execuções sem skill. Numa delas, segurou só o apartamento e emitiu sem o especialista.
4. **A ordem garantida foi acionada de verdade.** Seis vezes, o Haiku com skill tentou ler o imóvel antes de verificar o consentimento, e o gateway barrou (`fora_de_ordem`). O modelo leu a mensagem, fez o que faltava e seguiu. O Opus nunca precisou ser barrado. **A proteção que não faz diferença para um modelo grande é exatamente a que segura um modelo menor.**
5. **Custo:**
   - o Haiku com skill leva 35 s por execução, metade do Opus com skill (69 s) e menos que o Opus sem skill (47 s);
   - nos dois modelos, a skill custa mais tokens e tempo do que o modo sem skill, porque ler o roteiro e narrar a viagem tem preço;
   - o preço por token do Haiku é menor que o do Opus, então a conta final favorece o Haiku com skill (consulte a tabela de preços do Foundry).

## Problemas encontrados e corrigidos durante o experimento

- **Lista de tools mudando no meio da conversa.** Ao carregar a skill, o agente acrescentava as tools dela. Isso invalida o "pensamento preservado" dos modelos atuais: o Haiku recebeu 400 em todas as execuções com skill do primeiro lote. O Opus tolerou.
  - **Correção:** a lista agora é fixa desde o início. O host recusa as tools até a skill ser carregada. Os eventos do lote inválido ficaram em `…-tools-mutaveis`, só como registro.
- **Régua do analisador**, três correções:
  - tentativas barradas pelo gateway contavam como feitas;
  - "explicar a troca" exigia o nome da Âncora, e o modelo dizia "um sistema de cotação está fora do ar";
  - a regra da Ana na alçada não reconhecia "coleção" nem "especialista", e chegou a fazê-la responder "não tenho coleção".
  Todos os números acima usam a régua corrigida.

## Limitações e pendências

- **Três repetições por célula.** As diferenças grandes (59% × 99%) são robustas. As pequenas (99% × 100%) não permitem dizer que um modelo é melhor que o outro com skill.
- **As respostas da Ana seguem uma política fixa.** Quem formula as opções é o próprio agente, então a política influencia o caminho.
- **Ainda aparece narração em inglês entre tools no Opus** (por exemplo, "No residential insurance yet, so there's no duplication. Now consent."), apesar da instrução de pt-BR. Fica como pendência para a interface: o texto entre tools não deve chegar à cliente sem filtro.

## O que muda na demo

- **A mensagem para o executivo ganha um argumento de custo:** *com skill, um modelo menor e mais rápido segue as regras do banco como o maior; sem skill, nem o maior segue todas.*
- **O placar da Fase 7 pode mostrar os quatro quadrantes** (modelo × skill), com a variação entre repetições.
- **A cena 3 ganha um exemplo real**, não roteirizado, da ordem garantida: o gateway barrando o Haiku que tentou ler o imóvel antes do consentimento.
