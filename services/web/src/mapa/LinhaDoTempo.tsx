// A linha do tempo da jornada, no rodapé do mapa: espelha a faixa "As 9 paradas" do infográfico.
// Feita, atual ou pendente; em vermelho se um incidente apareceu ali. Acima, a narração do passo.

import { CheckmarkFilled, CircleDash, ErrorFilled, LocationFilled } from '@carbon/icons-react';

import { mensagens } from '../mensagens/pt-BR';
import type { ParadaDaRota } from '../tipos';
import type { EstadoDaViagem } from './viagem';

const t = mensagens.mapa.linhaDoTempo;

export function narracao(v: EstadoDaViagem): string {
  if (!v.id) return t.inicio;
  if (!v.modo) return t.preparando;
  if (v.fim) return v.fim.apolice ? t.chegou(v.fim.apolice) : t.parou(v.fim.status);
  const ultimoIncidente = v.incidentes.at(-1);
  const ferramenta = v.ultimaTool ? t.chamou(v.ultimaTool.tool) : '';
  if (v.paradaInfo) {
    const passo = t.parada(v.paradaInfo.numero, v.paradaInfo.nome);
    if (ultimoIncidente && ultimoIncidente.parada === v.parada) return `${passo} — ${ultimoIncidente.metafora}`;
    return ferramenta ? `${passo} — ${ferramenta}` : passo;
  }
  if (v.rota) return t.rotaPlanejada;
  return ferramenta ? `${t.semRota} — ${ferramenta}` : t.semRota;
}

export function LinhaDoTempo(props: { paradas: ParadaDaRota[]; viagem: EstadoDaViagem }) {
  const { viagem } = props;
  const visitadas = new Set(viagem.visitadas);
  const comIncidente = new Set(viagem.incidentes.map((i) => i.parada).filter(Boolean));
  const numeradas = props.paradas.filter((p) => p.numero != null);
  return (
    <div className="linha-do-tempo">
      <p className="linha-do-tempo__narracao" aria-live="polite">
        {narracao(viagem)}
      </p>
      <ol className="linha-do-tempo__paradas" aria-label={t.rotulo}>
        {numeradas.map((p) => {
          const estado = p.id === viagem.parada ? 'atual' : visitadas.has(p.id) ? 'feita' : 'pendente';
          const problema = comIncidente.has(p.id);
          const Icone = problema ? ErrorFilled : estado === 'atual' ? LocationFilled : estado === 'feita' ? CheckmarkFilled : CircleDash;
          return (
            <li
              key={p.id}
              className={`linha-do-tempo__parada linha-do-tempo__parada--${estado}${problema ? ' linha-do-tempo__parada--incidente' : ''}`}
              aria-current={estado === 'atual' ? 'step' : undefined}
            >
              <Icone className="linha-do-tempo__icone" aria-hidden />
              <span className="linha-do-tempo__numero">{p.numero}</span>
              <span className="linha-do-tempo__nome">{p.nome}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
