// A cidade em 3D, gerada a partir do grafo: bairros em relevo, prédios, árvores e a estrada
// da jornada. Os prédios genéricos são decoração, mas sempre os mesmos (semente fixa).
// O y do grafo cresce para baixo; na cena 3D, cresce para cima (o norte fica no topo).

import type { Bairro, Cidade, NoDoMapa, Ponto, RotaDaJornada } from '../tipos';

export type Ponto3 = [number, number, number];
export type Cor = [number, number, number, number];

export const ALTURA_DA_PLACA = 3; // os bairros são placas levemente elevadas
const AMOSTRAS_POR_TRECHO = 14;

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
const CINZA: Cor = [176, 176, 172, 255];

// Gerador pseudoaleatório determinístico (mulberry32).
function semente(n: number) {
  let a = n >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const hash = (texto: string) => [...texto].reduce((h, c) => (Math.imul(h, 31) + c.charCodeAt(0)) | 0, 7);

export function dentro([x, y]: Ponto, poligono: Ponto[]): boolean {
  let fora = true;
  for (let i = 0, j = poligono.length - 1; i < poligono.length; j = i++) {
    const [xi, yi] = poligono[i];
    const [xj, yj] = poligono[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) fora = !fora;
  }
  return !fora;
}

function distanciaAoSegmento([px, py]: Ponto, [ax, ay]: Ponto, [bx, by]: Ponto): number {
  const dx = bx - ax;
  const dy = by - ay;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy || 1)));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

const distanciaAoCaminho = (p: Ponto, caminho: Ponto[]) =>
  caminho.slice(1).reduce((m, b, i) => Math.min(m, distanciaAoSegmento(p, caminho[i], b)), Infinity);

export const centroDe = (pontos: Ponto[]): Ponto => [
  pontos.reduce((s, p) => s + p[0], 0) / pontos.length,
  pontos.reduce((s, p) => s + p[1], 0) / pontos.length,
];

// Catmull-Rom: a estrada passa por todas as paradas, em curva suave.
export function suavizar(pontos: Ponto[]): Ponto[] {
  if (pontos.length < 3) return pontos;
  const saida: Ponto[] = [];
  for (let i = 0; i < pontos.length - 1; i++) {
    const p0 = pontos[Math.max(i - 1, 0)];
    const p1 = pontos[i];
    const p2 = pontos[i + 1];
    const p3 = pontos[Math.min(i + 2, pontos.length - 1)];
    for (let k = 0; k < AMOSTRAS_POR_TRECHO; k++) {
      const t = k / AMOSTRAS_POR_TRECHO;
      const t2 = t * t;
      const t3 = t2 * t;
      const f = (a: number, b: number, c: number, d: number) =>
        0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
      saida.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
    }
  }
  saida.push(pontos[pontos.length - 1]);
  return saida;
}

export interface Caminho {
  pontos: Ponto3[];
  comprimentos: number[]; // acumulado, do início até cada ponto
  arcoDaParada: Map<string, number>;
  total: number;
}

export interface BairroCena {
  id: string;
  nome: string;
  poligono: Ponto[]; // coordenadas do grafo
  centro: Ponto3;
  cor: Cor;
  pastel: Cor;
}

export interface Predio {
  bairro: string;
  base: Ponto3[]; // pegada retangular, na altura da placa
  altura: number;
  cor: Cor;
}

export interface Arvore {
  bairro: string;
  posicao: Ponto3;
}

export interface Cena3D {
  ponto: (x: number, y: number, z?: number) => Ponto3;
  mundo: { largura: number; altura: number };
  bairros: BairroCena[];
  predios: Predio[];
  arvores: Arvore[];
  rio: Ponto3[];
  avenidas: { de: string; para: string; caminho: Ponto3[] }[];
  nos: Map<string, NoDoMapa>;
  bairroDe: (x: number, y: number) => string | null; // x, y já na cena
}

// As rotas compartilham paradas: um pequeno deslocamento separa as estradas.
const DESLOCAMENTO: Record<string, number> = { 'rota-rapida': -6, 'rota-economica': 0, 'rota-assistida': 6 };

export function caminhoDaRota(rota: RotaDaJornada, cena: Cena3D, z = ALTURA_DA_PLACA + 0.6): Caminho {
  const d = DESLOCAMENTO[rota.id] ?? 0;
  const paradas = rota.paradas.filter((p) => cena.nos.has(p.id));
  const brutos: Ponto[] = paradas.map((p) => {
    const n = cena.nos.get(p.id)!;
    return [n.x + d, n.y + d];
  });
  const suaves = suavizar(brutos);
  const pontos = suaves.map(([x, y]) => cena.ponto(x, y, z));
  const comprimentos = [0];
  for (let i = 1; i < pontos.length; i++)
    comprimentos.push(
      comprimentos[i - 1] + Math.hypot(pontos[i][0] - pontos[i - 1][0], pontos[i][1] - pontos[i - 1][1]),
    );
  const arcoDaParada = new Map<string, number>();
  paradas.forEach((p, i) => {
    const indice = Math.min(i * AMOSTRAS_POR_TRECHO, pontos.length - 1);
    if (!arcoDaParada.has(p.id)) arcoDaParada.set(p.id, comprimentos[indice]);
  });
  return { pontos, comprimentos, arcoDaParada, total: comprimentos[comprimentos.length - 1] ?? 0 };
}

export function pontoNoCaminho(c: Caminho, s: number): Ponto3 {
  if (!c.pontos.length) return [0, 0, 0];
  if (s <= 0) return c.pontos[0];
  if (s >= c.total) return c.pontos[c.pontos.length - 1];
  let i = 1;
  while (c.comprimentos[i] < s) i++;
  const a = c.pontos[i - 1];
  const b = c.pontos[i];
  const t = (s - c.comprimentos[i - 1]) / (c.comprimentos[i] - c.comprimentos[i - 1] || 1);
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

export const suave = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);

export function montarCena(cidade: Cidade, rotas: RotaDaJornada[]): Cena3D {
  const { altura } = cidade.mundo;
  const ponto = (x: number, y: number, z = 0): Ponto3 => [x, altura - y, z];
  const nos = new Map(cidade.nos.map((n) => [n.id, n]));
  const centros = new Map(cidade.bairros.map((b) => [b.id, centroDe(b.poligono)]));

  const bairros: BairroCena[] = cidade.bairros.map((b: Bairro) => {
    const cor = hex(b.cor);
    const [cx, cy] = centros.get(b.id)!;
    return {
      id: b.id,
      nome: b.nome,
      poligono: b.poligono,
      centro: ponto(cx, cy, ALTURA_DA_PLACA),
      cor,
      pastel: misturar(cor, BRANCO, 0.6),
    };
  });

  // Onde não pode ter prédio: avenidas, estradas da jornada e os próprios nós (sistemas e paradas).
  const avenidas = cidade.avenidas
    .filter((a) => centros.has(a.de) && centros.has(a.para))
    .map((a) => ({ de: a.de, para: a.para, bruto: [centros.get(a.de)!, centros.get(a.para)!] as Ponto[] }));
  const estradas = rotas.map((r) =>
    suavizar(r.paradas.filter((p) => nos.has(p.id)).map((p) => [nos.get(p.id)!.x, nos.get(p.id)!.y] as Ponto)),
  );
  const livre = (p: Ponto) =>
    avenidas.every((a) => distanciaAoCaminho(p, a.bruto) > 9) &&
    estradas.every((e) => distanciaAoCaminho(p, e) > 12) &&
    distanciaAoCaminho(p, cidade.rio) > 16 &&
    cidade.nos.every((n) => Math.hypot(n.x - p[0], n.y - p[1]) > 9);

  const predios: Predio[] = [];
  const arvores: Arvore[] = [];
  for (const b of cidade.bairros) {
    const aleatorio = semente(hash(b.id));
    const xs = b.poligono.map((p) => p[0]);
    const ys = b.poligono.map((p) => p[1]);
    const cor = hex(b.cor);
    for (let x = Math.min(...xs) + 10; x < Math.max(...xs) - 6; x += 19) {
      for (let y = Math.min(...ys) + 10; y < Math.max(...ys) - 6; y += 19) {
        const p: Ponto = [x + (aleatorio() - 0.5) * 6, y + (aleatorio() - 0.5) * 6];
        // Margem até a borda da placa.
        const folga = [
          [p[0] - 7, p[1] - 7],
          [p[0] + 7, p[1] + 7],
          [p[0] - 7, p[1] + 7],
          [p[0] + 7, p[1] - 7],
        ] as Ponto[];
        if (!folga.every((q) => dentro(q, b.poligono)) || !livre(p)) continue;
        const sorte = aleatorio();
        if (sorte < 0.28) {
          arvores.push({ bairro: b.id, posicao: ponto(p[0], p[1], ALTURA_DA_PLACA) });
          continue;
        }
        const w = 4 + aleatorio() * 3;
        const d = 4 + aleatorio() * 3;
        const [bx, by] = [p[0], p[1]];
        predios.push({
          bairro: b.id,
          base: [
            ponto(bx - w, by - d, ALTURA_DA_PLACA),
            ponto(bx + w, by - d, ALTURA_DA_PLACA),
            ponto(bx + w, by + d, ALTURA_DA_PLACA),
            ponto(bx - w, by + d, ALTURA_DA_PLACA),
          ],
          altura: 6 + aleatorio() ** 2 * 34,
          cor: misturar(cor, BRANCO, 0.35 + aleatorio() * 0.35),
        });
      }
    }
  }

  return {
    ponto,
    mundo: cidade.mundo,
    bairros,
    predios,
    arvores,
    rio: cidade.rio.map(([x, y]) => ponto(x, y, 0.4)),
    avenidas: avenidas.map((a) => ({
      de: a.de,
      para: a.para,
      caminho: a.bruto.map(([x, y]) => ponto(x, y, ALTURA_DA_PLACA + 0.3)),
    })),
    nos,
    bairroDe: (x, y) => cidade.bairros.find((b) => dentro([x, altura - y], b.poligono))?.id ?? null,
  };
}

// Prédios-sistema, no bairro aberto: altura e forma pela categoria do nó.
const ALTURA_POR_TIPO: Record<string, number> = {
  Sistema: 46,
  ApiCotacao: 40,
  ApiEmissao: 40,
  Fila: 30,
  Canal: 30,
  SLA: 22,
  Seguradora: 34,
  Especialista: 18,
  MeioPagamento: 20,
  Politica: 26,
  Norma: 24,
  BaseLegal: 22,
  ExigenciaRegistro: 20,
  FinalidadeDados: 18,
  RegraElegibilidade: 24,
  RegraAdequacao: 24,
  LimiteAlcada: 22,
  AreaRisco: 16,
  Score: 18,
  ProdutoSeguro: 30,
  Cobertura: 16,
  Assistencia: 14,
  Franquia: 12,
};

export const alturaDoSistema = (n: NoDoMapa) => ALTURA_POR_TIPO[n.tipo] ?? 14;

export function pegada(n: NoDoMapa, cena: Cena3D, z = ALTURA_DA_PLACA, raio = 6): Ponto3[] {
  return [
    cena.ponto(n.x - raio, n.y - raio, z),
    cena.ponto(n.x + raio, n.y - raio, z),
    cena.ponto(n.x + raio, n.y + raio, z),
    cena.ponto(n.x - raio, n.y + raio, z),
  ];
}

export function octogono(x: number, y: number, z: number, raio: number): Ponto3[] {
  return Array.from({ length: 8 }, (_, i) => {
    const a = (i / 8) * Math.PI * 2 + Math.PI / 8;
    return [x + Math.cos(a) * raio, y + Math.sin(a) * raio, z] as Ponto3;
  });
}

export const corDoSistema = (bairro: BairroCena | undefined): Cor =>
  bairro ? misturar(bairro.cor, BRANCO, 0.2) : CINZA;
