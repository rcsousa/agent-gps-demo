// O painel do apresentador: uma gaveta no próprio mapa (tecla P).
// Prepara as cenas, muda o mundo pelo simulador, decide o pedágio e fala pela Ana.
// Tudo o que ele faz vai ao simulador (o mundo) ou à resposta da Ana: nunca roteiriza o agente.

import { ArrowRight, Book, Close, Play, Renew, Reset } from '@carbon/icons-react';
import { Button, IconButton, InlineNotification, Tag, Toggle } from '@carbon/react';
import { useCallback, useEffect, useState } from 'react';

import { api, simulador } from '../api';
import type { EstadoDaViagem } from '../mapa/viagem';
import { mensagens } from '../mensagens/pt-BR';
import { navegar } from '../navegacao';
import { definirTelao, useTelao } from '../telao';
import type { IncidenteDoSimulador, TicketDeAprovacao } from '../tipos';
import { abrirBastidores } from '../bastidores/PainelDeBastidores';
import { type Cena, CAPITULO_DAS_CENAS, CENAS } from './cenas';

const t = mensagens.apresentador;
const PRAZO_DO_PEDAGIO_S = 30; // depois disso, a especialista Marina aprova sozinha (simulador)
const INTERVALO_MS = 2000;

export function Apresentador(props: {
  aberto: boolean;
  aoFechar: () => void;
  cenaAtual: string | null;
  real: EstadoDaViagem; // a viagem em curso: a pergunta pendente e o id para responder
  aoResponder: (texto: string) => Promise<void>;
  gravacoes: Record<string, string>; // cena → nome da gravação (replay)
  aguardando: boolean; // o robô espera num balão (passo a passo)
  aoSeguir: () => void;
}) {
  const [curta, setCurta] = useState(false);
  const telao = useTelao();
  const [incidentes, setIncidentes] = useState<IncidenteDoSimulador[]>([]);
  const [tickets, setTickets] = useState<TicketDeAprovacao[]>([]);
  const [fora, setFora] = useState<string[]>([]);
  const [aviso, setAviso] = useState<{ tipo: 'info' | 'error'; texto: string } | null>(null);
  const [agora, setAgora] = useState(() => Date.now());

  const atualizar = useCallback(async () => {
    try {
      const [i, a, f] = await Promise.all([simulador.incidentes(), simulador.aprovacoes(), simulador.toolsFora()]);
      setIncidentes(i);
      setTickets(a.filter((x) => x.status === 'pendente'));
      setFora(f.fora);
      setAgora(Date.now());
    } catch {
      setAviso({ tipo: 'error', texto: t.erro });
    }
  }, []);

  useEffect(() => {
    if (!props.aberto) return;
    atualizar();
    const id = setInterval(atualizar, INTERVALO_MS);
    return () => clearInterval(id);
  }, [props.aberto, atualizar]);

  async function agir(caminho: string) {
    try {
      await simulador.acao(caminho);
      await atualizar();
    } catch {
      setAviso({ tipo: 'error', texto: t.erro });
    }
  }

  // Escolher uma cena: mundo limpo e o preset no mapa. A viagem só começa no "Iniciar viagem".
  async function escolher(c: Cena, replay = false) {
    await agir('/reset');
    const busca = new URLSearchParams({ cena: c.numero });
    if (c.raioX) busca.set('visao', 'raio-x');
    if (replay && props.gravacoes[c.numero]) {
      busca.set('gravacao', props.gravacoes[c.numero]);
    } else if (c.ultimaViagemComSkill) {
      const placar = await api.placar().catch(() => null);
      const ultima = placar?.sessao.execucoes.find((e) => e.modo === 'com_skill');
      if (!ultima) {
        setAviso({ tipo: 'info', texto: t.semViagemComSkill });
        return;
      }
      busca.set('execucao', ultima.id);
    }
    navegar(`/mapa?${busca.toString()}`);
    setAviso(replay || c.ultimaViagemComSkill ? null : { tipo: 'info', texto: t.cenaPronta(c.numero) });
  }

  if (!props.aberto) return null;
  const sugerido = CENAS.find((c) => c.numero === props.cenaAtual)?.incidente;
  const falas = (props.cenaAtual && t.falasPorCena[props.cenaAtual]) || [];

  return (
    <aside className="apresentador" aria-label={t.titulo}>
      <header className="apresentador__cabecalho">
        <div>
          <h2 className="apresentador__titulo">{t.titulo}</h2>
          <span className="apagado">{t.atalho}</span>
        </div>
        <IconButton kind="ghost" label={t.fechar} align="left" onClick={props.aoFechar}>
          <Close />
        </IconButton>
      </header>

      <Toggle
        id="modo-telao"
        size="sm"
        labelText={t.modoTelao}
        hideLabel
        labelA={t.modoTelao}
        labelB={t.modoTelao}
        toggled={telao.ligado}
        onToggle={definirTelao}
      />
      <Button
        size="md"
        renderIcon={ArrowRight}
        className="apresentador__seguir"
        disabled={!props.aguardando}
        onClick={props.aoSeguir}
        title={props.aguardando ? undefined : t.semBalao}
      >
        {t.seguirJornada}
      </Button>

      {aviso && (
        <InlineNotification
          kind={aviso.tipo}
          lowContrast
          title={aviso.texto}
          onClose={() => setAviso(null)}
          className="apresentador__aviso"
        />
      )}

      <section className="apresentador__secao">
        <div className="apresentador__linha">
          <h3>{t.cenas}</h3>
          <Toggle id="versao-curta" size="sm" labelText={t.versaoCurta} hideLabel labelA={t.versaoCurta} labelB={t.versaoCurta} toggled={curta} onToggle={setCurta} />
        </div>
        <ol className="apresentador__cenas">
          {CENAS.filter((c) => !curta || c.curta).map((c) => (
            <li key={c.numero} className={c.numero === props.cenaAtual ? 'apresentador__cena--atual' : ''}>
              <span className="apresentador__numero">{c.numero}</span>
              <span className="apresentador__nome">
                {t.nomes[c.numero]}
                <small>{t.minutos(c.minutos)}</small>
              </span>
              <IconButton size="sm" kind="primary" label={`${t.aoVivo}: ${t.nomes[c.numero]}`} onClick={() => escolher(c)}>
                <Play />
              </IconButton>
              <IconButton
                size="sm"
                kind="ghost"
                label={`${mensagens.bastidores.daCena} ${c.numero}`}
                onClick={() =>
                  abrirBastidores({
                    capitulo: CAPITULO_DAS_CENAS,
                    ancora: `cena-${c.numero}`,
                    titulo: mensagens.bastidores.cena(c.numero, t.nomes[c.numero]),
                  })
                }
              >
                <Book />
              </IconButton>
              <IconButton
                size="sm"
                kind="tertiary"
                label={props.gravacoes[c.numero] ? `${t.replay}: ${t.nomes[c.numero]}` : t.semGravacao}
                disabled={!props.gravacoes[c.numero]}
                onClick={() => escolher(c, true)}
              >
                <Renew />
              </IconButton>
            </li>
          ))}
        </ol>
      </section>

      {falas.length > 0 && (
        <section className="apresentador__secao">
          <h3>{t.falas}</h3>
          <p className="apagado">{props.real.pergunta ? t.falasAjuda : t.semPergunta}</p>
          {falas.map((fala) => (
            <Button
              key={fala}
              kind="tertiary"
              size="sm"
              className="apresentador__fala"
              disabled={!props.real.pergunta}
              onClick={() => props.aoResponder(fala)}
            >
              {fala}
            </Button>
          ))}
        </section>
      )}

      <section className="apresentador__secao">
        <h3>{t.pedagio}</h3>
        {!tickets.length && <p className="apagado">{t.semTicket}</p>}
        {tickets.map((k) => {
          const restante = Math.max(
            0,
            PRAZO_DO_PEDAGIO_S - Math.floor((agora - new Date(k.criado_em).getTime()) / 1000),
          );
          return (
            <div key={k.ticket_id} className="apresentador__ticket">
              <span>{t.ticket(k.premio_anual, k.importancia_segurada)}</span>
              <span className="apagado">{k.motivo}</span>
              <span className="apagado">{t.marinaEm(restante)}</span>
              <div className="apresentador__botoes">
                <Button size="sm" onClick={() => agir(`/aprovacoes/${k.ticket_id}/aprovar`)}>
                  {t.aprovar}
                </Button>
                <Button size="sm" kind="danger--tertiary" onClick={() => agir(`/aprovacoes/${k.ticket_id}/recusar`)}>
                  {t.recusar}
                </Button>
              </div>
            </div>
          );
        })}
      </section>

      <section className="apresentador__secao">
        <div className="apresentador__linha">
          <h3>{t.incidentes}</h3>
          <Button size="sm" kind="ghost" renderIcon={Reset} onClick={() => agir('/reset')} title={t.mundoLimpoAjuda}>
            {t.mundoLimpo}
          </Button>
        </div>
        <ul className="apresentador__incidentes">
          {incidentes.map((i) => (
            <li key={i.id} className={i.id === sugerido ? 'apresentador__incidente--sugerido' : ''}>
              <Toggle
                id={`incidente-${i.id}`}
                size="sm"
                labelText={i.nome}
                hideLabel
                labelA={t.inativo}
                labelB={t.ativo}
                toggled={i.ativo}
                onToggle={(ligar: boolean) => agir(`/incidentes/${i.id}/${ligar ? 'aplicar' : 'remover'}`)}
              />
              <span className="apresentador__incidente">
                <strong>{i.nome}</strong>
                <Tag size="sm" type={i.ativo ? 'red' : 'cool-gray'}>
                  {i.metafora}
                </Tag>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="apresentador__secao">
        <div className="apresentador__linha">
          <h3>{t.toolsFora}</h3>
          {fora.length > 0 && (
            <Button size="sm" kind="ghost" onClick={() => agir('/tools/religar-todas')}>
              {t.religarTodas}
            </Button>
          )}
        </div>
        {fora.length ? (
          <ul>
            {fora.map((nome) => (
              <li key={nome} className="raiox__mono">
                {nome}
              </li>
            ))}
          </ul>
        ) : (
          <p className="apagado">{t.nenhumaToolFora}</p>
        )}
      </section>
    </aside>
  );
}
