// O caminho do robô pelas ruas da grade, como num GPS: só ângulos retos, pelo meio da rua.
// Toda porta fica numa rua horizontal (y numa linha da grade); as placas das paradas, nas esquinas.

import type { Grade, Ponto } from '../tipos';

const comprimento = (pontos: Ponto[]) =>
  pontos.slice(1).reduce((s, p, i) => s + Math.abs(p[0] - pontos[i][0]) + Math.abs(p[1] - pontos[i][1]), 0);

// As esquinas nas pontas do trecho de rua onde o ponto está (uma só, se ele já é uma esquina).
function esquinasVizinhas(p: Ponto, grade: Grade): Ponto[] {
  const { xs } = grade;
  if (xs.includes(p[0])) return [p];
  const k = xs.findIndex((x) => x > p[0]);
  return [
    [xs[Math.max(k - 1, 0)], p[1]],
    [xs[Math.min(k, xs.length - 1)], p[1]],
  ];
}

// Entre duas esquinas: anda na horizontal pela rua de saída e depois na vertical.
const emL = (a: Ponto, b: Ponto): Ponto[] => [a, [b[0], a[1]], b];

function limpar(pontos: Ponto[]): Ponto[] {
  const saida: Ponto[] = [];
  for (const p of pontos) {
    const ultimo = saida.at(-1);
    if (ultimo && ultimo[0] === p[0] && ultimo[1] === p[1]) continue;
    // Tira o ponto do meio quando três seguidos estão na mesma reta.
    const penultimo = saida.at(-2);
    if (
      ultimo &&
      penultimo &&
      ((penultimo[0] === ultimo[0] && ultimo[0] === p[0]) || (penultimo[1] === ultimo[1] && ultimo[1] === p[1]))
    )
      saida.pop();
    saida.push(p);
  }
  return saida;
}

export function caminhoPelasRuas(de: Ponto, para: Ponto, grade: Grade): Ponto[] {
  if (de[1] === para[1]) return limpar([de, para]); // na mesma rua: em linha reta
  let melhor: Ponto[] | null = null;
  for (const a of esquinasVizinhas(de, grade)) {
    for (const b of esquinasVizinhas(para, grade)) {
      const caminho = limpar([de, ...emL(a, b), para]);
      if (!melhor || comprimento(caminho) < comprimento(melhor)) melhor = caminho;
    }
  }
  return melhor ?? [de, para];
}

export interface Trajeto {
  pontos: Ponto[];
  acumulado: number[]; // distância percorrida até cada ponto
  total: number;
}

export function trajeto(pontos: Ponto[]): Trajeto {
  const acumulado = [0];
  for (let i = 1; i < pontos.length; i++)
    acumulado.push(acumulado[i - 1] + Math.hypot(pontos[i][0] - pontos[i - 1][0], pontos[i][1] - pontos[i - 1][1]));
  return { pontos, acumulado, total: acumulado.at(-1) ?? 0 };
}

export function pontoNoTrajeto(t: Trajeto, s: number): Ponto {
  if (s <= 0 || t.pontos.length < 2) return t.pontos[0];
  if (s >= t.total) return t.pontos[t.pontos.length - 1];
  let i = 1;
  while (t.acumulado[i] < s) i++;
  const a = t.pontos[i - 1];
  const b = t.pontos[i];
  const f = (s - t.acumulado[i - 1]) / (t.acumulado[i] - t.acumulado[i - 1] || 1);
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}

// O tempo de um trecho na tela: proporcional à distância, entre 0,6 s e 1,8 s.
export const duracaoDoTrecho = (distancia: number) => Math.min(Math.max(600 + distancia * 1.6, 600), 1800);
