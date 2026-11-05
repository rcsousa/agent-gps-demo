// O balão de fala do robô, preso acima do pino: o anúncio do GPS. Quando o mapa espera, traz o "Seguir".

import { ArrowRight, Compass, ErrorFilled } from '@carbon/icons-react';
import { Button } from '@carbon/react';

import { mensagens } from '../mensagens/pt-BR';
import type { Balao as DadosDoBalao } from './baloes';

const t = mensagens.mapa.baloes;
// Os anúncios que são a voz do GPS (os de sistema chamado e de incidente são do caminho).
const DO_GPS = new Set(['apresentacao', 'roteiro', 'rota', 'parada', 'recalculo', 'pedagio', 'pergunta', 'chegada']);
const MEIA_LARGURA = 170; // o balão tem no máximo 20rem de largura
const ALTURA_DO_PINO = 80; // o balão abre acima do pino do robô
const ALTURA_MINIMA = 150; // espaço para o balão abaixo da borda de cima

export function Balao(props: {
  balao: DadosDoBalao;
  posicao: [number, number]; // o robô, na tela
  largura: number;
  escala: number; // o modo telão aumenta o balão
  aguardando: boolean;
  aoSeguir: () => void;
}) {
  const { balao } = props;
  const [x, y] = props.posicao;
  const meia = MEIA_LARGURA * props.escala;
  const esquerda = Math.min(Math.max(x, meia + 8), props.largura - meia - 8);
  const topo = Math.max(y - ALTURA_DO_PINO * props.escala, ALTURA_MINIMA * props.escala);
  const rabicho = Math.min(Math.max(x - esquerda, -meia + 20), meia - 20);
  return (
    <div
      className={`balao balao--${balao.tipo}${balao.ok ? '' : ' balao--erro'}`}
      style={{ left: esquerda, top: topo, ['--rabicho' as string]: `${rabicho}px` }}
      role="status"
      aria-live="polite"
    >
      {DO_GPS.has(balao.tipo) && (
        <span className="balao__gps">
          <Compass size={12} aria-hidden /> {t.gps}
        </span>
      )}
      <p className="balao__texto">
        {!balao.ok && <ErrorFilled className="balao__icone" aria-hidden />}
        {balao.texto}
      </p>
      {balao.subtexto && <p className="balao__subtexto">{balao.subtexto}</p>}
      {balao.detalhe && <code className="balao__detalhe">{balao.detalhe}</code>}
      {props.aguardando && (
        <Button size="sm" kind="primary" renderIcon={ArrowRight} onClick={props.aoSeguir} className="balao__seguir">
          {t.seguir} <kbd>{t.atalho}</kbd>
        </Button>
      )}
    </div>
  );
}
