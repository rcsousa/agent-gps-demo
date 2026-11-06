// O balão de fala do robô, preso acima do pino: o anúncio do GPS. Quando o mapa espera, traz o "Seguir".

import { ArrowRight, Compass, ErrorFilled } from '@carbon/icons-react';
import { Button } from '@carbon/react';
import { useLayoutEffect, useRef, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';
import type { Balao as DadosDoBalao } from './baloes';

const t = mensagens.mapa.baloes;
// Os anúncios que são a voz do GPS (os de sistema chamado e de incidente são do caminho).
const DO_GPS = new Set(['apresentacao', 'roteiro', 'rota', 'parada', 'recalculo', 'pedagio', 'pergunta', 'chegada']);
const MEIA_LARGURA = 170; // o balão tem no máximo 20rem de largura
const ALTURA_DO_PINO = 80; // o balão abre acima do pino do robô
const ALTURA_MINIMA = 150; // espaço para o balão abaixo da borda de cima, até medir o balão
const FOLGA_NO_TOPO = 8;
const DISTANCIA_ABAIXO = 16; // abaixo do robô, o balão abre logo depois do pé do pino

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
  // Os anúncios têm alturas diferentes (o porquê, a regra, o botão): o balão mede a própria altura
  // para nunca passar da borda de cima do mapa, onde o começo do anúncio ficaria cortado.
  const elemento = useRef<HTMLDivElement>(null);
  const [altura, setAltura] = useState(ALTURA_MINIMA * props.escala);
  useLayoutEffect(() => {
    if (elemento.current) setAltura(elemento.current.offsetHeight);
  }, [balao, props.aguardando, props.escala]);
  const meia = MEIA_LARGURA * props.escala;
  const esquerda = Math.min(Math.max(x, meia + 8), props.largura - meia - 8);
  // Acima do pino, se couber; senão, abaixo do robô (o rabicho vira para cima), sem cobri-lo.
  const acima = y - ALTURA_DO_PINO * props.escala;
  const abaixo = acima < altura + FOLGA_NO_TOPO;
  const topo = abaixo ? y + DISTANCIA_ABAIXO * props.escala : acima;
  const rabicho = Math.min(Math.max(x - esquerda, -meia + 20), meia - 20);
  return (
    <div
      ref={elemento}
      className={`balao balao--${balao.tipo}${balao.ok ? '' : ' balao--erro'}${abaixo ? ' balao--abaixo' : ''}`}
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
