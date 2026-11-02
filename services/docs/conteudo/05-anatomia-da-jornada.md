# 5. Anatomia da jornada de seguro

!!! abstract "Resumo executivo"
    A Ana pede pelo app: "quero contratar um seguro residencial para meu apartamento". Do pedido até a apólice emitida, o agente passa por **9 paradas**, sempre pelo mapa. A demo oferece três caminhos:

    - **Rota rápida:** cerca de 5 min.
    - **Rota econômica:** cerca de 7 min, com o menor prêmio.
    - **Rota assistida:** cerca de 12 min, com um especialista humano no meio.

    As estimativas não são desenhadas à mão: saem do estado atual do mapa.

## Aprofundamento técnico

### A personagem e os clientes-cenário

A Ana é a personagem padrão. Outros 7 clientes existem para que cada incidente da spec tenha alguém real no mapa:

| Cliente | Cenário | Incidente que prepara |
| --- | --- | --- |
| Ana Ribeiro | padrão | — |
| Bruno Teixeira | consentimento vencido em agosto | Contramão |
| Carla Nogueira | sobrado na várzea do Tietê | Desvio por obra (vistoria) |
| Diego Martins | cobertura de R$ 4,2 milhões | Pedágio (alçada) |
| Elisa Prado | cadastro vindo de planilha legada | Ponte interditada (proveniência fraca) |
| Fábio, Gabriela, Helena | neutros | Dão volume ao bairro |

```yaml
--8<-- "instancias/cliente.yaml:ana"
```

### As paradas

Cada parada mora no bairro do trecho que executa. O mapa dá zoom nesse bairro quando o agente chega lá. O campo `tempo_base_s` é a duração típica da parada.

```yaml
--8<-- "instancias/jornada.yaml:paradas"
```

A **vistoria** e a **aprovação do especialista** são paradas opcionais. Elas entram na rota quando uma regra pede.

### As rotas

As três rotas passam pelas mesmas nove paradas. A assistida entra pela aprovação do especialista antes do pagamento. Diagrama gerado das instâncias da ontologia:

![As 9 paradas e as 3 rotas](assets/diagramas/rotas.svg)

```yaml
--8<-- "instancias/jornada.yaml:rotas"
```

`consultar_rota` calcula a estimativa de cada rota assim:

- **Tempo:** soma do `tempo_base_s` das paradas, mais o tempo adicional da rota, mais a latência atual de tudo o que a rota usa (sistemas e APIs).
- **Custo operacional:** soma do `custo_estimado` das APIs e sistemas usados.
- **Risco:**
  - parte do risco-base da rota;
  - sobe um nível se algo no caminho estiver **degradado**;
  - vai para **alto**, e a rota aparece como **bloqueada**, se algo estiver **fora do ar**.

Com o estado-base, o resultado é este:

| Rota | Tempo | Prêmio de referência | Risco |
| --- | --- | --- | --- |
| Rápida (Âncora) | ~5 min | R$ 320/ano | baixo |
| Econômica (as três) | ~7 min | R$ 280/ano | baixo |
| Assistida (Farol + especialista) | ~12 min | R$ 310/ano | médio |

### As regras no caminho

Os produtos residenciais exigem regras de elegibilidade e adequação, e estão sujeitos à alçada automática:

```yaml
--8<-- "instancias/produtos.yaml:exigencias"
```

O pedágio aparece quando o prêmio passa da alçada automática:

```yaml
--8<-- "instancias/risco.yaml:alcadas"
```

```yaml
--8<-- "instancias/risco.yaml:pedagio"
```

O uso de dados pessoais precisa de base legal (LGPD):

```yaml
--8<-- "instancias/regulatorio.yaml:finalidades"
```

### As skills que percorrem a jornada

A skill `contratacao-seguro-residencial` conduz as 9 paradas. Ela chama as outras três nos trechos certos: consentimento na parada 3, cotação multisseguradora na rota econômica e escalonamento humano no pedágio. Trecho real do `SKILL.md`:

```markdown
--8<-- "contratacao-seguro-residencial/SKILL.md:36:65"
```

Quando o caminho muda, a skill manda ler `references/desvios.md`, que traz uma regra de recálculo para cada incidente:

```markdown
--8<-- "contratacao-seguro-residencial/references/desvios.md"
```
