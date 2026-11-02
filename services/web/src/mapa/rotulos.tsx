// Rótulos do mapa em HTML (IBM Plex, legíveis no telão), presos a pontos da cena 3D.
// Os que se sobreporiam ficam de fora, por prioridade: incidente, parada, bairro, sistema.

import { ErrorFilled, WarningAltFilled } from '@carbon/icons-react';

import type { Ponto3 } from './cidade3d';

export interface Rotulo {
  id: string;
  tipo: 'bairro' | 'parada' | 'incidente' | 'sistema' | 'pedagio';
  texto: string;
  posicao: Ponto3;
  prioridade: number; // menor entra primeiro
  numero?: number | null;
  status?: 'ok' | 'degradado' | 'fora' | null;
  estado?: 'atual' | 'feita' | 'pendente' | 'esmaecido';
  abaixo?: boolean; // o chip fica abaixo do ponto (o espaço de cima é do robô)
  aoClicar?: () => void;
}

const LETRA = { bairro: 10.5, parada: 8, incidente: 8, sistema: 8, pedagio: 8 };
const ALTURA = { bairro: 32, parada: 28, incidente: 28, sistema: 26, pedagio: 28 };

export function Rotulos(props: {
  rotulos: Rotulo[];
  projetar: (p: Ponto3) => [number, number];
  largura: number;
  altura: number;
  reservado?: [number, number, number, number][]; // áreas da tela que nenhum rótulo cobre (o robô)
}) {
  const colocados: [number, number, number, number][] = [...(props.reservado ?? [])];
  const visiveis: { r: Rotulo; x: number; y: number }[] = [];
  for (const r of [...props.rotulos].sort((a, b) => a.prioridade - b.prioridade)) {
    const [px, py] = props.projetar(r.posicao);
    const largura = r.texto.length * LETRA[r.tipo] + 28 + (r.numero != null ? 22 : 0) + (r.status ? 20 : 0);
    const altura = ALTURA[r.tipo];
    // O ponto precisa estar na tela; o chip é empurrado para dentro dela, se passar da borda.
    if (px < 0 || px > props.largura) continue;
    const x = Math.min(Math.max(px - largura / 2, 4), props.largura - largura - 4);
    const y = r.abaixo ? py + 8 : py - altura - 6;
    if (y < 0 || y + altura > props.altura) continue;
    const caixa: [number, number, number, number] = [x - 3, y - 3, x + largura + 3, y + altura + 3];
    if (colocados.some((o) => caixa[0] < o[2] && caixa[2] > o[0] && caixa[1] < o[3] && caixa[3] > o[1])) continue;
    colocados.push(caixa);
    visiveis.push({ r, x, y });
  }

  return (
    <div className="rotulos" aria-hidden={false}>
      {visiveis.map(({ r, x, y }) => {
        const classe = `rotulo rotulo--${r.tipo}${r.estado ? ` rotulo--${r.estado}` : ''}${
          r.status && r.status !== 'ok' ? ` rotulo--${r.status}` : ''
        }`;
        const conteudo = (
          <>
            {r.numero != null && <span className="rotulo__numero">{r.numero}</span>}
            {r.status === 'fora' && <ErrorFilled className="rotulo__icone" aria-label="fora do ar" />}
            {r.status === 'degradado' && <WarningAltFilled className="rotulo__icone" aria-label="lentidão" />}
            <span className="rotulo__texto">{r.texto}</span>
          </>
        );
        const estilo = { transform: `translate(${x}px, ${y}px)` };
        return r.aoClicar ? (
          <button key={r.id} type="button" className={classe} style={estilo} onClick={r.aoClicar} data-rotulo={r.id}>
            {conteudo}
          </button>
        ) : (
          <span key={r.id} className={classe} style={estilo} data-rotulo={r.id}>
            {conteudo}
          </span>
        );
      })}
    </div>
  );
}
