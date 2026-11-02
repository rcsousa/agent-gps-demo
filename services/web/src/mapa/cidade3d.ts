// A cidade em 3D, desenhada da grade e do grafo: ruas, avenidas, calçadas, lotes e uma construção
// para cada lugar do grafo. Nada é decorativo além das praças nos lotes vazios.
// O y do grafo cresce para baixo; na cena 3D, cresce para cima (o norte fica no topo).

import type { Bairro, Cidade, Estilo, Grade, NoDoMapa, Ponto } from '../tipos';

export type Ponto3 = [number, number, number];
export type Cor = [number, number, number, number];

export const Z_RUA = 0.4;
export const Z_CALCADA = 0.9; // as quadras são um pouco mais altas que a rua
export const Z_CHAO = 1.0; // onde as construções se apoiam
const FOLGA_ENTRE_LOTES = 4;

export const hex = (cor: string, alfa = 255): Cor => [
  parseInt(cor.slice(1, 3), 16),
  parseInt(cor.slice(3, 5), 16),
  parseInt(cor.slice(5, 7), 16),
  alfa,
];

export function misturar(a: Cor, b: Cor, t: number, alfa = 255): Cor {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, alfa];
}

const BRANCO: Cor = [255, 255, 255, 255];
const GRAMA: Cor = [166, 196, 140, 255];

// Pseudoaleatório determinístico por texto: a mesma construção tem sempre a mesma variação.
function sorte(texto: string): number {
  let h = 2166136261;
  for (const c of texto) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return ((h >>> 0) % 1000) / 1000;
}

export const suave = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

export interface BairroCena {
  id: string;
  nome: string;
  cor: Cor;
  pastel: Cor;
  centro: Ponto3;
}

export interface Retangulo3 {
  poligono: Ponto3[];
  cor: Cor;
}

export interface Construcao {
  no: NoDoMapa;
  estilo: Estilo;
  posicao: Ponto3;
  escala: [number, number, number];
  yaw: number; // 0: a frente para o norte da cena; 180: para o sul
  cor: Cor;
}

export interface Cena3D {
  ponto: (x: number, y: number, z?: number) => Ponto3;
  mundo: { largura: number; altura: number };
  grade: Grade;
  bairros: BairroCena[];
  ruas: Retangulo3[];
  faixas: { caminho: Ponto3[]; avenida: boolean }[];
  calcadas: Retangulo3[];
  lotes: Retangulo3[];
  agua: Retangulo3[];
  arvores: Ponto3[];
  rio: Ponto3[];
  construcoes: Construcao[];
  nos: Map<string, NoDoMapa>;
  bairroDe: (x: number, y: number) => string | null; // x, y já na cena
}

export function montarCena(cidade: Cidade): Cena3D {
  const { largura, altura } = cidade.mundo;
  const grade = cidade.cidade;
  const ponto = (x: number, y: number, z = 0): Ponto3 => [x, altura - y, z];
  const retangulo = (x0: number, y0: number, x1: number, y1: number, z: number): Ponto3[] => [
    ponto(x0, y0, z),
    ponto(x1, y0, z),
    ponto(x1, y1, z),
    ponto(x0, y1, z),
  ];
  const nos = new Map(cidade.nos.map((n) => [n.id, n]));
  const corDoBairro = new Map(cidade.bairros.map((b) => [b.id, hex(b.cor)]));
  const pastel = (b: string) => misturar(corDoBairro.get(b) ?? [150, 150, 150, 255], BRANCO, 0.72);

  const bairros: BairroCena[] = cidade.bairros.map((b: Bairro) => {
    const xs = b.poligono.map((p) => p[0]);
    const ys = b.poligono.map((p) => p[1]);
    const cor = hex(b.cor);
    return {
      id: b.id,
      nome: b.nome,
      cor,
      pastel: misturar(cor, BRANCO, 0.72),
      centro: ponto((Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2, Z_CHAO),
    };
  });

  // Ruas: uma faixa de asfalto por linha da grade; as avenidas são mais largas.
  const asfalto: Cor = [96, 98, 104, 255];
  const avenida = (k: number, verticais: boolean) =>
    (verticais ? grade.avenidas_verticais : grade.avenidas_horizontais).includes(k);
  const ruas: Retangulo3[] = [];
  const faixas: Cena3D['faixas'] = [];
  grade.xs.forEach((x, k) => {
    const w = avenida(k, true) ? grade.avenida : grade.rua;
    ruas.push({ poligono: retangulo(x - w / 2, 0, x + w / 2, altura, Z_RUA), cor: asfalto });
    faixas.push({ caminho: [ponto(x, 0, Z_RUA + 0.05), ponto(x, altura, Z_RUA + 0.05)], avenida: avenida(k, true) });
  });
  grade.ys.forEach((y, k) => {
    const w = avenida(k, false) ? grade.avenida : grade.rua;
    ruas.push({ poligono: retangulo(0, y - w / 2, largura, y + w / 2, Z_RUA), cor: asfalto });
    faixas.push({ caminho: [ponto(0, y, Z_RUA + 0.05), ponto(largura, y, Z_RUA + 0.05)], avenida: avenida(k, false) });
  });

  // Quadras: calçada clara e lotes na cor do bairro; os vazios viram praças.
  const ocupantes = cidade.nos.filter((n) => n.estilo && n.estilo !== 'placa');
  const ocupado = (cx: number, cy: number) => ocupantes.some((n) => Math.abs(n.x - cx) < 1.5 && Math.abs(n.y - cy) < 1.5);
  const calcadas: Retangulo3[] = [];
  const lotes: Retangulo3[] = [];
  const arvores: Ponto3[] = [];
  const [lx, ly] = [2, 2];
  const agua: Retangulo3[] = [];
  for (const q of grade.quadras) {
    if (q.agua) {
      // As quadras que o rio cruza viram água por inteiro (as ruas passam por cima, como pontes).
      const [x0, y0, x1, y1] = q.retangulo;
      agua.push({ poligono: retangulo(x0 - 6, y0 - 6, x1 + 6, y1 + 6, 0.2), cor: [120, 176, 222, 255] });
      continue;
    }
    const [x0, y0, x1, y1] = q.retangulo;
    calcadas.push({ poligono: retangulo(x0, y0, x1, y1, 0), cor: [222, 218, 208, 255] });
    const lw = (x1 - x0 - (lx - 1) * FOLGA_ENTRE_LOTES) / lx;
    const lh = (y1 - y0 - (ly - 1) * FOLGA_ENTRE_LOTES) / ly;
    for (let b = 0; b < ly; b++) {
      for (let a = 0; a < lx; a++) {
        const cx = x0 + a * (lw + FOLGA_ENTRE_LOTES) + lw / 2;
        const cy = y0 + b * (lh + FOLGA_ENTRE_LOTES) + lh / 2;
        const temConstrucao = ocupado(cx, cy);
        const m = 1.5;
        lotes.push({
          poligono: retangulo(cx - lw / 2 + m, cy - lh / 2 + m, cx + lw / 2 - m, cy + lh / 2 - m, Z_CALCADA + 0.05),
          cor: temConstrucao ? pastel(q.bairro) : GRAMA,
        });
        if (!temConstrucao) {
          // Praça: duas ou três árvores em posições fixas.
          const s = sorte(`${q.coluna}-${q.linha}-${a}-${b}`);
          const n = s < 0.5 ? 2 : 3;
          for (let i = 0; i < n; i++) {
            const ang = s * 6.28 + (i * 6.28) / n;
            arvores.push(ponto(cx + Math.cos(ang) * lw * 0.22, cy + Math.sin(ang) * lh * 0.22, Z_CALCADA));
          }
        }
      }
    }
  }

  const [larguraDoLote, alturaDoLote] = grade.lote;
  const construcoes: Construcao[] = cidade.nos
    .filter((n): n is NoDoMapa & { estilo: Estilo } => Boolean(n.estilo))
    .map((n) => {
      const placa = n.estilo === 'placa';
      const variacao = 0.85 + sorte(n.id) * 0.3;
      // A frente da construção dá para a rua da porta: no grafo, porta acima = norte da cena.
      const yaw = n.porta && n.porta[1] > n.y ? 180 : 0;
      return {
        no: n,
        estilo: n.estilo,
        posicao: ponto(n.x, n.y, placa ? Z_RUA : Z_CHAO),
        escala: placa ? [40, 40, 1] : [larguraDoLote, alturaDoLote, variacao],
        yaw,
        cor: misturar(corDoBairro.get(n.bairro) ?? [150, 150, 150, 255], BRANCO, 0.25 + sorte(`${n.id}*`) * 0.25),
      };
    });

  return {
    ponto,
    mundo: cidade.mundo,
    grade,
    bairros,
    ruas,
    faixas,
    calcadas,
    lotes,
    agua,
    arvores,
    rio: cidade.rio.map(([x, y]) => ponto(x, y, 0.2)),
    construcoes,
    nos,
    bairroDe: (x, y) => {
      const b = cidade.bairros.find((bairro) => {
        const xs = bairro.poligono.map((p) => p[0]);
        const ys = bairro.poligono.map((p) => p[1]);
        const gy = altura - y;
        return x >= Math.min(...xs) && x <= Math.max(...xs) && gy >= Math.min(...ys) && gy <= Math.max(...ys);
      });
      return b?.id ?? null;
    },
  };
}

export const pontoDaPorta = (n: NoDoMapa): Ponto => n.porta ?? [n.x, n.y];
