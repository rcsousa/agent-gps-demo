// O balão de fala do robô, preso acima do pino. No passo a passo, traz o botão "Seguir".

import { ArrowRight, ErrorFilled } from '@carbon/icons-react';
import { Button } from '@carbon/react';

import { mensagens } from '../mensagens/pt-BR';
import type { Balao as DadosDoBalao } from './baloes';

const t = mensagens.mapa.baloes;
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
      <p className="balao__texto">
        {!balao.ok && <ErrorFilled className="balao__icone" aria-hidden />}
        {balao.texto}
      </p>
      {balao.detalhe && <code className="balao__detalhe">{balao.detalhe}</code>}
      {props.aguardando && (
        <Button size="sm" kind="primary" renderIcon={ArrowRight} onClick={props.aoSeguir} className="balao__seguir">
          {t.seguir} <kbd>{t.atalho}</kbd>
        </Button>
      )}
    </div>
  );
}
