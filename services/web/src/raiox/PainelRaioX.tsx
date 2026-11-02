// O painel do Modo Raio-X: tudo o que trafegou na viagem, inspecionável.
// Abas do infográfico: Chamadas MCP, Conversa, Proveniência, Métricas e Placar.

import { CheckmarkFilled, ErrorFilled, Locked } from '@carbon/icons-react';
import { CodeSnippet, Link, Tab, TabList, TabPanel, TabPanels, Tabs } from '@carbon/react';
import { type MouseEvent, useEffect, useMemo, useRef, useState } from 'react';

import { abrirBastidores } from '../bastidores/PainelDeBastidores';
import { mensagens } from '../mensagens/pt-BR';
import { Conversa, RespostaDaAna } from '../mapa/Paineis';
import { type EstadoDaViagem, noDaTool } from '../mapa/viagem';
import { PainelLateral } from '../status/Painel';
import type { NoDoMapa } from '../tipos';
import { Placar } from './Placar';
import { metricas, type Registro, registros } from './registros';

const t = mensagens.raioX;

function IconeDoStatus({ status }: { status: Registro['status'] }) {
  if (status === 'ok') return <CheckmarkFilled className="raiox__icone raiox__icone--ok" aria-label="ok" />;
  if (status === 'bloqueio') return <Locked className="raiox__icone raiox__icone--bloqueio" aria-label="bloqueio" />;
  if (status === 'erro') return <ErrorFilled className="raiox__icone raiox__icone--erro" aria-label="erro" />;
  return <span className="raiox__icone" />;
}

function Chamadas(props: { lista: Registro[]; aoAbrir: (r: Registro) => void }) {
  // O log acompanha a viagem: a cada linha nova, rola até o fim (a não ser que alguém esteja lendo acima).
  const fim = useRef<HTMLLIElement>(null);
  const seguindo = useRef(true);
  useEffect(() => {
    const aba = fim.current?.closest('.raiox__aba');
    if (!aba) return;
    const aoRolar = () => (seguindo.current = aba.scrollHeight - aba.scrollTop - aba.clientHeight < 80);
    aba.addEventListener('scroll', aoRolar);
    return () => aba.removeEventListener('scroll', aoRolar);
  }, [props.lista.length > 0]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (seguindo.current) fim.current?.scrollIntoView({ block: 'nearest' });
  }, [props.lista.length]);
  if (!props.lista.length) return <p className="apagado">{t.semExecucao}</p>;
  return (
    <ol className="raiox__log" aria-live="polite">
      {props.lista.map((r) => (
        <li key={r.indice}>
          <button
            type="button"
            className={`raiox__linha raiox__linha--${r.tipo}${r.status === 'bloqueio' ? ' raiox__linha--bloqueio' : ''}`}
            onClick={() => props.aoAbrir(r)}
          >
            <IconeDoStatus status={r.status} />
            <span className="raiox__titulo">{r.titulo}</span>
            {r.duracaoMs != null && <span className="raiox__duracao">{r.duracaoMs} ms</span>}
            {r.detalhe && <span className="raiox__detalhe">{r.detalhe}</span>}
          </button>
        </li>
      ))}
      <li ref={fim} aria-hidden />
    </ol>
  );
}

function Proveniencia(props: { viagem: EstadoDaViagem; nos: Map<string, NoDoMapa>; aoEscolherNo: (id: string) => void }) {
  const p = t.proveniencia;
  const decisoes = props.viagem.eventos.filter((e) =>
    ['route.planned', 'route.recalculated', 'incident.detected'].includes(e.tipo),
  );
  const tocados = new Map<string, number>();
  for (const e of props.viagem.eventos.filter((x) => x.tipo === 'tool.called')) {
    const no = noDaTool(e.dados.tool, e.dados.argumentos);
    if (no) tocados.set(no, (tocados.get(no) ?? 0) + 1);
  }
  return (
    <div className="raiox__secoes">
      <section>
        <h3 className="raiox__secao">{p.decisoes}</h3>
        {!decisoes.length && <p className="apagado">{p.nenhuma}</p>}
        <ul className="raiox__decisoes">
          {decisoes.map((e, i) => (
            <li key={i} className={`raiox__decisao raiox__decisao--${e.tipo.split('.')[1]}`}>
              <strong>
                {e.tipo === 'route.planned' ? p.rota : e.tipo === 'route.recalculated' ? p.recalculo : p.incidente}
                {e.tipo === 'route.planned' && ` · ${e.dados.nome ?? e.dados.rota}`}
                {e.tipo === 'route.recalculated' && ` · ${e.dados.de} → ${e.dados.para}`}
                {e.tipo === 'incident.detected' && ` · ${e.dados.metafora}`}
              </strong>
              <span>{e.dados.motivo ?? e.dados.descricao}</span>
              {e.dados.regra && (
                <span className="apagado">
                  {p.regra}: {e.dados.regra}
                </span>
              )}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h3 className="raiox__secao">{p.tocados}</h3>
        <p className="apagado">{p.tocadosAjuda}</p>
        <ul className="raiox__tocados">
          {[...tocados.entries()].map(([id, vezes]) => (
            <li key={id}>
              <Link
                href="#"
                onClick={(evento: MouseEvent) => {
                  evento.preventDefault();
                  props.aoEscolherNo(id);
                }}
              >
                {props.nos.get(id)?.nome ?? id}
              </Link>
              <span className="apagado"> · {props.nos.get(id)?.tipo_exibicao} · {p.vezes(vezes)}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Metricas({ viagem }: { viagem: EstadoDaViagem }) {
  const m = useMemo(() => metricas(viagem.eventos), [viagem.eventos]);
  const tm = t.metricas;
  const n = (v: number) => v.toLocaleString('pt-BR');
  return (
    <div className="raiox__secoes">
      <dl className="raiox__numeros">
        <div>
          <dt>{tm.tokensEntrada}</dt>
          <dd>
            {n(m.totais.entrada + m.totais.cache)}
            <small> ({n(m.totais.cache)} {tm.tokensCache})</small>
          </dd>
        </div>
        <div>
          <dt>{tm.tokensSaida}</dt>
          <dd>{n(m.totais.saida)}</dd>
        </div>
        <div>
          <dt>{tm.tempoModelo}</dt>
          <dd>{tm.segundos(m.totais.modeloMs)}</dd>
        </div>
        <div>
          <dt>{tm.tempoTools}</dt>
          <dd>{tm.segundos(m.totais.toolsMs)}</dd>
        </div>
        <div>
          <dt>{tm.custo}</dt>
          <dd>{tm.usd(m.custo)}</dd>
        </div>
        <div>
          <dt>{tm.regras}</dt>
          <dd>{m.regras ? `${m.regras.cumpridas}/${m.regras.total}` : '—'}</dd>
        </div>
      </dl>
      {m.caso && <p className="apagado">{tm.caso(m.caso)}</p>}
      {m.regras && (
        <Link
          href="#"
          onClick={(evento: MouseEvent) => {
            evento.preventDefault();
            abrirBastidores({
              capitulo: '06-arquitetura',
              ancora: 'o-placar-regras-conferidas-nos-eventos',
              titulo: mensagens.bastidores.placar,
            });
          }}
        >
          {mensagens.bastidores.porQueRegras}
        </Link>
      )}
      {m.regras && (
        <ul className="raiox__regras">
          {Object.entries(m.regras.regras).map(([nome, ok]) => (
            <li key={nome}>
              {ok ? (
                <CheckmarkFilled className="raiox__icone raiox__icone--ok" />
              ) : (
                <ErrorFilled className="raiox__icone raiox__icone--erro" />
              )}
              {nome}
            </li>
          ))}
        </ul>
      )}
      <h3 className="raiox__secao">{tm.porPasso}</h3>
      <table className="raiox__tabela">
        <thead>
          <tr>
            <th>{tm.passo}</th>
            <th>{tm.entrada}</th>
            <th>{tm.saida}</th>
            <th>{tm.duracao}</th>
            <th>{tm.tools}</th>
          </tr>
        </thead>
        <tbody>
          {m.passos.map((p) => (
            <tr key={p.passo}>
              <td>{p.passo}</td>
              <td>{n(p.entrada + p.cache)}</td>
              <td>{n(p.saida)}</td>
              <td>{tm.segundos(p.duracaoMs)}</td>
              <td>{p.tools}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3 className="raiox__secao">{tm.porTool}</h3>
      <table className="raiox__tabela">
        <thead>
          <tr>
            <th>{tm.tool}</th>
            <th>{tm.chamadas}</th>
            <th>{tm.media}</th>
            <th>{tm.erros}</th>
          </tr>
        </thead>
        <tbody>
          {m.tools.map((x) => (
            <tr key={x.tool}>
              <td className="raiox__mono">{x.tool}</td>
              <td>{x.chamadas}</td>
              <td>{x.mediaMs} ms</td>
              <td>{x.erros}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PainelRaioX(props: {
  viagem: EstadoDaViagem; // o que o diretor já exibiu: o log acompanha o mapa
  conversa: EstadoDaViagem; // a conversa real, sem atraso
  nos: Map<string, NoDoMapa>;
  aoResponder: (texto: string) => Promise<void>;
  aoEscolherNo: (id: string) => void;
  abaInicial?: number;
}) {
  const [aberto, setAberto] = useState<Registro | null>(null);
  const lista = useMemo(() => registros(props.viagem.eventos), [props.viagem.eventos]);
  const fimDaViagem = props.conversa.fim ? props.conversa.id : null;
  return (
    <section className="raiox" aria-label={t.raioX}>
      {props.conversa.pergunta && (
        <RespostaDaAna pergunta={props.conversa.pergunta} aoResponder={props.aoResponder} compacta />
      )}
      <Tabs defaultSelectedIndex={props.abaInicial ?? 0}>
        <TabList aria-label={t.raioX} contained>
          <Tab>{t.abas.chamadas}</Tab>
          <Tab>{t.abas.conversa}</Tab>
          <Tab>{t.abas.proveniencia}</Tab>
          <Tab>{t.abas.metricas}</Tab>
          <Tab>{t.abas.placar}</Tab>
        </TabList>
        <TabPanels>
          <TabPanel className="raiox__aba">
            <Chamadas lista={lista} aoAbrir={setAberto} />
          </TabPanel>
          <TabPanel className="raiox__aba raiox__aba--conversa">
            <Conversa viagem={props.conversa} aoResponder={props.aoResponder} embutida />
          </TabPanel>
          <TabPanel className="raiox__aba">
            <Proveniencia viagem={props.viagem} nos={props.nos} aoEscolherNo={props.aoEscolherNo} />
          </TabPanel>
          <TabPanel className="raiox__aba">
            <Metricas viagem={props.viagem} />
          </TabPanel>
          <TabPanel className="raiox__aba">
            <Placar atualizarCom={fimDaViagem} />
          </TabPanel>
        </TabPanels>
      </Tabs>
      {aberto && (
        <PainelLateral tipo={t.payload} titulo={aberto.titulo} aoFechar={() => setAberto(null)}>
          <p className="apagado">{t.evento(aberto.evento.tipo, aberto.evento.origem)}</p>
          <CodeSnippet type="multi" feedback="Copiado" wrapText maxCollapsedNumberOfRows={40}>
            {JSON.stringify(aberto.evento, null, 2)}
          </CodeSnippet>
        </PainelLateral>
      )}
    </section>
  );
}
