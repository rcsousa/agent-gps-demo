---
name: verificacao-consentimento
description: Verifica se há base legal (LGPD) para usar os dados de uma cliente numa finalidade e, se o consentimento estiver vencido, pede a renovação pelo app. Trecho reutilizável, chamado por outras skills antes de qualquer uso de dados pessoais.
allowed-tools: consentimento.verificar consentimento.solicitar_renovacao contexto.consultar_regras contexto.consultar_proveniencia
metadata:
  versao: "1.0"
  usa-skills: ""
  aprovacao-humana: não se aplica
---

# Verificação de consentimento

Use antes de usar dados pessoais da cliente para oferta ou para compartilhar com parceiros.

1. Para cada finalidade pedida, chame `consentimento.verificar`. Finalidades:
   - `finalidade-oferta-personalizada`: usar dados de relacionamento para sugerir seguros;
   - `finalidade-compartilhamento-seguradoras`: enviar dados do imóvel às seguradoras;
   - `finalidade-cobranca`: debitar o prêmio (base: execução do contrato).
2. `permitido: true`: siga. Guarde a base legal; ela entra no registro da decisão.
3. `permitido: false`, com consentimento vencido:
   - diga à cliente, em uma frase, que o consentimento venceu e por que ele é necessário;
   - chame `consentimento.solicitar_renovacao`;
   - aguarde alguns segundos e chame `consentimento.verificar` de novo;
   - só siga com `permitido: true`. Se continuar negado, encerre a oferta com cordialidade.
4. `permitido: false`, sem consentimento algum: não peça renovação. Explique que precisamos do aceite dela no app e encerre a oferta.

Para explicar a regra, `contexto.consultar_regras` com `parada-consentimento` mostra a base legal e a política de privacidade que a sustentam.
