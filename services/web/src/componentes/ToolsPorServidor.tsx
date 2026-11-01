import { CheckmarkFilled, ErrorFilled, Renew } from '@carbon/icons-react';
import { Accordion, AccordionItem, Button, InlineNotification, Tag, Toggle } from '@carbon/react';
import { useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';
import type { Ferramenta, Servico } from '../tipos';

const t = mensagens.tools;

// Ligar e desligar é ação do apresentador sobre o mundo: vai ao simulador, nunca ao agente.
async function mudarTool(caminho: string): Promise<void> {
  const resposta = await fetch(`/simulador/tools/${caminho}`, { method: 'POST' });
  if (!resposta.ok) throw new Error(String(resposta.status));
}

function LinhaTool(props: {
  tool: Ferramenta;
  fora: boolean;
  pendente: boolean;
  aoMudar: (qualificado: string, noAr: boolean) => void;
}) {
  const { tool, fora } = props;
  return (
    <li className="tools__linha">
      <code className="tools__nome">{tool.nome}</code>
      {tool.qualificado ? (
        <span className="tools__gateway">
          {t.visivelComo} <code>{tool.qualificado}</code>
        </span>
      ) : (
        <Tag type="warm-gray" size="sm">
          {t.oculta}
        </Tag>
      )}
      {tool.qualificado && (
        <div className="tools__controle">
          {fora ? (
            <Tag type="red" renderIcon={ErrorFilled}>
              {t.foraDoAr}
            </Tag>
          ) : (
            <Tag type="green" renderIcon={CheckmarkFilled}>
              {t.noAr}
            </Tag>
          )}
          <Toggle
            id={`tool-${tool.qualificado}`}
            size="sm"
            labelText={t.rotuloToggle(tool.qualificado)}
            hideLabel
            labelA={t.foraDoAr}
            labelB={t.noAr}
            toggled={!fora}
            disabled={props.pendente}
            onToggle={(noAr: boolean) => props.aoMudar(tool.qualificado!, noAr)}
          />
        </div>
      )}
    </li>
  );
}

export function ToolsPorServidor(props: { servicos: Servico[]; aoMudar: () => Promise<void> }) {
  // Resposta imediata na tela; a próxima consulta ao status confirma o estado real.
  const [otimista, setOtimista] = useState<Record<string, boolean>>({});
  const [pendentes, setPendentes] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState(false);

  const estaFora = (tool: Ferramenta) =>
    tool.qualificado !== null && tool.qualificado in otimista ? otimista[tool.qualificado] : tool.fora;
  const totalFora = props.servicos.flatMap((s) => s.ferramentas).filter(estaFora).length;

  async function executar(acao: () => Promise<void>, nomes: string[]) {
    setPendentes((p) => new Set([...p, ...nomes]));
    try {
      await acao();
      setErro(false);
    } catch {
      setErro(true);
    }
    await props.aoMudar();
    setOtimista((o) => Object.fromEntries(Object.entries(o).filter(([n]) => !nomes.includes(n))));
    setPendentes((p) => new Set([...p].filter((n) => !nomes.includes(n))));
  }

  function alternar(qualificado: string, noAr: boolean) {
    setOtimista((o) => ({ ...o, [qualificado]: !noAr }));
    executar(() => mudarTool(`${qualificado}/${noAr ? 'religar' : 'desligar'}`), [qualificado]);
  }

  function religarTodas() {
    const nomes = props.servicos.flatMap((s) => s.ferramentas).filter(estaFora).map((f) => f.qualificado!);
    setOtimista((o) => ({ ...o, ...Object.fromEntries(nomes.map((n) => [n, false])) }));
    executar(() => mudarTool('religar-todas'), nomes);
  }

  return (
    <section className="tools" aria-labelledby="titulo-tools">
      <div className="status__cabecalho">
        <div>
          <h2 id="titulo-tools" className="status__grupo">
            {t.titulo}
          </h2>
          <p className="status__descricao">{t.descricao}</p>
        </div>
        <div className="status__acoes">
          <span aria-live="polite">{t.contagemFora(totalFora)}</span>
          <Button kind="tertiary" size="md" renderIcon={Renew} disabled={totalFora === 0} onClick={religarTodas}>
            {t.religarTodas}
          </Button>
        </div>
      </div>

      {erro && (
        <InlineNotification
          kind="error"
          lowContrast
          title={t.erroAcao}
          subtitle={t.erroAcaoDetalhe}
          onClose={() => setErro(false)}
        />
      )}

      <Accordion className="tools__lista" align="start">
        {props.servicos.map((servico) => {
          const visiveis = servico.ferramentas.filter((f) => f.visivel).length;
          const fora = servico.ferramentas.filter(estaFora).length;
          return (
            <AccordionItem
              key={servico.nome}
              title={
                <span className="tools__titulo">
                  <strong>{mensagens.servicos[servico.nome] ?? servico.nome}</strong>
                  <code>{servico.nome}</code>
                  <span className="tools__resumo">{t.resumoServidor(visiveis, fora, servico.prompts.length)}</span>
                </span>
              }
            >
              <ul>
                {servico.ferramentas.map((tool) => (
                  <LinhaTool
                    key={tool.nome}
                    tool={tool}
                    fora={estaFora(tool)}
                    pendente={tool.qualificado !== null && pendentes.has(tool.qualificado)}
                    aoMudar={alternar}
                  />
                ))}
                {servico.prompts.map((prompt) => (
                  <li key={prompt} className="tools__linha">
                    <code className="tools__nome">{prompt.split('.').slice(1).join('.')}</code>
                    <span className="tools__gateway">
                      {t.promptNoGateway} <code>{prompt}</code>
                    </span>
                  </li>
                ))}
              </ul>
            </AccordionItem>
          );
        })}
      </Accordion>
    </section>
  );
}
