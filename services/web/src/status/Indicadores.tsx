// Linha de indicadores do topo: a saúde da plataforma num relance.

import { CheckmarkFilled, ErrorFilled, Information } from '@carbon/icons-react';
import { Tag, Tile } from '@carbon/react';
import type { ReactNode } from 'react';

import { mensagens } from '../mensagens/pt-BR';
import type { Status } from '../tipos';

const t = mensagens.indicadores;

function Indicador(props: { titulo: string; valor: ReactNode; tecnico?: string; rodape: ReactNode }) {
  return (
    <Tile className="indicador">
      <span className="indicador__titulo">{props.titulo}</span>
      <span className="indicador__valor">{props.valor}</span>
      {props.tecnico && <span className="indicador__tecnico">{props.tecnico}</span>}
      <span className="indicador__rodape">{props.rodape}</span>
    </Tile>
  );
}

function Situacao(props: { ok: boolean; texto: string }) {
  return props.ok ? (
    <Tag type="green" size="sm" renderIcon={CheckmarkFilled}>
      {props.texto}
    </Tag>
  ) : (
    <Tag type="red" size="sm" renderIcon={ErrorFilled}>
      {props.texto}
    </Tag>
  );
}

export function Indicadores({ status }: { status: Status }) {
  // Plataforma (gateway e barramento) mais os servidores MCP atrás do gateway.
  const total = status.servicos.length + 2;
  const noAr =
    status.servicos.filter((s) => s.status === 'ok').length +
    (status.gateway === 'ok' ? 1 : 0) +
    (status.barramento === 'ok' ? 1 : 0);

  return (
    <div className="indicadores">
      <Indicador
        titulo={t.servicos}
        valor={`${noAr}/${total}`}
        rodape={<Situacao ok={noAr === total} texto={t.servicosDetalhe(noAr, total)} />}
      />
      <Indicador
        titulo={t.tools}
        valor={status.ferramentas}
        rodape={<Situacao ok={!status.ferramentas_fora} texto={t.toolsDetalhe(status.ferramentas_fora)} />}
      />
      <Indicador titulo={t.skills} valor={status.skills} rodape={<span>{t.skillsDetalhe}</span>} />
      <Indicador titulo={t.prompts} valor={status.prompts} rodape={<span>{t.promptsDetalhe}</span>} />
      <Indicador
        titulo={t.llm}
        valor={t.provedores[status.llm.provedor] ?? status.llm.provedor}
        tecnico={[status.llm.modelo, status.llm.plataforma && t.plataformas[status.llm.plataforma]]
          .filter(Boolean)
          .join(' · ')}
        rodape={
          status.llm.configurado ? (
            <Situacao ok texto={t.llmConfigurado} />
          ) : (
            <Tag type="warm-gray" size="sm" renderIcon={Information}>
              {t.llmAusente}
            </Tag>
          )
        }
      />
      <Indicador
        titulo={t.barramento}
        valor={status.barramento === 'ok' ? mensagens.estado.noAr : mensagens.estado.foraDoAr}
        rodape={<span className="indicador__tecnico">{t.barramentoDetalhe}</span>}
      />
    </div>
  );
}
