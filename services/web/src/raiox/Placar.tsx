// O placar da cena 8: regras do banco cumpridas, tempo e custo.
// Nesta demo (as viagens da sessão) e na referência (o experimento com os modelos reais).

import { InlineLoading } from '@carbon/react';
import { useEffect, useState } from 'react';

import { api } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import type { ExecucaoNoPlacar, LinhaDoPlacar, Placar as DadosDoPlacar } from '../tipos';

const t = mensagens.raioX.placar;
const tm = mensagens.raioX.metricas;
const MODOS = ['sem_contexto', 'sem_skill', 'com_skill'];
const nomeDoModo = (m: string) => mensagens.mapa.barra.modos[m as keyof typeof mensagens.mapa.barra.modos] ?? m;
const nomeDoModelo = (m: string) => mensagens.mapa.barra.modelo(m);

// Barra de regras: o número sempre ao lado; a cor nunca sozinha.
function Barra({ cumpridas, total }: { cumpridas: number; total: number }) {
  const fracao = total ? cumpridas / total : 0;
  const nivel = fracao >= 0.95 ? 'alta' : fracao >= 0.75 ? 'media' : 'baixa';
  return (
    <span className="placar__barra" aria-label={`${t.percentual(cumpridas, total)} (${t.fracao(cumpridas, total)})`}>
      <span className={`placar__preenchido placar__preenchido--${nivel}`} style={{ inlineSize: `${fracao * 100}%` }} />
      <span className="placar__rotulo">
        {t.percentual(cumpridas, total)} <small>({t.fracao(cumpridas, total)})</small>
      </span>
    </span>
  );
}

function Tabela({ linhas }: { linhas: LinhaDoPlacar[] }) {
  return (
    <table className="raiox__tabela placar__tabela">
      <thead>
        <tr>
          <th>{t.modelo}</th>
          <th>{t.modo}</th>
          <th>{t.regras}</th>
          <th>{t.perfeitas}</th>
          <th>{t.tempo}</th>
          <th>{t.custo}</th>
        </tr>
      </thead>
      <tbody>
        {linhas.map((l) => (
          <tr key={`${l.modelo}-${l.modo}`} className={l.modo === 'com_skill' ? 'placar__destaque' : ''}>
            <td>{nomeDoModelo(l.modelo)}</td>
            <td>{nomeDoModo(l.modo)}</td>
            <td>
              <Barra cumpridas={l.cumpridas} total={l.total} />
            </td>
            <td>
              {l.perfeitas}/{l.execucoes}
            </td>
            <td>{l.segundos_medio.toLocaleString('pt-BR')} s</td>
            <td>{tm.usd(l.custo_medio_usd)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// A comparação da cena 8: a última viagem de cada modo, lado a lado.
function UltimasPorModo({ execucoes }: { execucoes: ExecucaoNoPlacar[] }) {
  const ultimas = MODOS.map((m) => execucoes.find((e) => e.modo === m)).filter(
    (e): e is ExecucaoNoPlacar => Boolean(e),
  );
  return (
    <div className="placar__cartoes">
      {ultimas.map((e) => (
        <div key={e.id} className={`placar__cartao placar__cartao--${e.modo}`}>
          <span className="placar__modo">{nomeDoModo(e.modo)}</span>
          <Barra cumpridas={e.cumpridas} total={e.total} />
          <span className="apagado">
            {nomeDoModelo(e.modelo)} · {e.segundos.toLocaleString('pt-BR')} s · {tm.usd(e.custo_usd)}
          </span>
          <span className="apagado">
            {t.caso}: {e.caso}
          </span>
        </div>
      ))}
    </div>
  );
}

export function Placar(props: { atualizarCom: string | null }) {
  const [dados, setDados] = useState<DadosDoPlacar | null>(null);
  useEffect(() => {
    api.placar().then(setDados, () => setDados(null));
  }, [props.atualizarCom]);
  if (!dados) return <InlineLoading />;
  const { sessao, referencia } = dados;
  return (
    <div className="raiox__secoes placar" data-testid="placar">
      <h3 className="raiox__secao">{t.titulo}</h3>
      <section>
        <h4 className="placar__subtitulo">{t.sessao}</h4>
        <p className="apagado">{t.sessaoAjuda}</p>
        {sessao.execucoes.length ? (
          <>
            <UltimasPorModo execucoes={sessao.execucoes} />
            <Tabela linhas={[...sessao.agregado].sort((a, b) => MODOS.indexOf(a.modo) - MODOS.indexOf(b.modo))} />
          </>
        ) : (
          <p>{t.vazia}</p>
        )}
      </section>
      <section>
        <h4 className="placar__subtitulo">{t.referencia}</h4>
        <p className="apagado">
          {t.fonte(new Date(referencia.data).toLocaleDateString('pt-BR', { timeZone: 'UTC' }))} · {referencia.descricao}
        </p>
        <Tabela linhas={referencia.linhas} />
      </section>
    </div>
  );
}
