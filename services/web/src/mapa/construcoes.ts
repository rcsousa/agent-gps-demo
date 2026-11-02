// As construções da cidade: uma forma por estilo (casa, loja, shopping, fábrica, prédio público,
// torre, prédio técnico, escritório e a placa das paradas), montadas em código como malhas 3D.
// Cada estilo tem duas partes: o corpo (na cor do bairro) e o detalhe (telhado, toldo, chaminé…),
// desenhadas por duas camadas SimpleMeshLayer. X e Y vão de -0,5 a 0,5 (frações do lote);
// Z está em unidades do mundo. A frente fica em +Y.

import type { Estilo } from '../tipos';

type V = [number, number, number];

export interface Malha {
  attributes: { positions: { value: Float32Array; size: 3 }; normals: { value: Float32Array; size: 3 } };
}

class Construtor {
  private pos: number[] = [];
  private nor: number[] = [];

  // Triângulo com normal plana, virada para fora do centro de referência da peça.
  tri(a: V, b: V, c: V, centro: V) {
    const u: V = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const w: V = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    let n: V = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]];
    const m = Math.hypot(...n) || 1;
    n = [n[0] / m, n[1] / m, n[2] / m];
    const g: V = [(a[0] + b[0] + c[0]) / 3 - centro[0], (a[1] + b[1] + c[1]) / 3 - centro[1], (a[2] + b[2] + c[2]) / 3 - centro[2]];
    if (n[0] * g[0] + n[1] * g[1] + n[2] * g[2] < 0) {
      n = [-n[0], -n[1], -n[2]];
      [b, c] = [c, b];
    }
    for (const p of [a, b, c]) this.pos.push(...p);
    for (let i = 0; i < 3; i++) this.nor.push(...n);
  }

  quad(a: V, b: V, c: V, d: V, centro: V) {
    this.tri(a, b, c, centro);
    this.tri(a, c, d, centro);
  }

  caixa(x0: number, y0: number, z0: number, x1: number, y1: number, z1: number) {
    const c: V = [(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2];
    const p = (x: number, y: number, z: number): V => [x, y, z];
    this.quad(p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1), p(x0, y1, z1), c); // topo
    this.quad(p(x0, y0, z0), p(x1, y0, z0), p(x1, y0, z1), p(x0, y0, z1), c); // fundo
    this.quad(p(x0, y1, z0), p(x1, y1, z0), p(x1, y1, z1), p(x0, y1, z1), c); // frente
    this.quad(p(x0, y0, z0), p(x0, y1, z0), p(x0, y1, z1), p(x0, y0, z1), c); // esquerda
    this.quad(p(x1, y0, z0), p(x1, y1, z0), p(x1, y1, z1), p(x1, y0, z1), c); // direita
    return this;
  }

  // Telhado de duas águas, com a cumeeira ao longo de X.
  duasAguas(x0: number, y0: number, x1: number, y1: number, z0: number, z1: number) {
    const ym = (y0 + y1) / 2;
    const c: V = [(x0 + x1) / 2, ym, z0];
    this.quad([x0, y0, z0], [x1, y0, z0], [x1, ym, z1], [x0, ym, z1], c);
    this.quad([x0, y1, z0], [x1, y1, z0], [x1, ym, z1], [x0, ym, z1], c);
    this.tri([x0, y0, z0], [x0, y1, z0], [x0, ym, z1], c);
    this.tri([x1, y0, z0], [x1, y1, z0], [x1, ym, z1], c);
    return this;
  }

  // Frontão (triângulo em pé) ao longo de X, na frente do prédio público.
  frontao(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) {
    const xm = (x0 + x1) / 2;
    const c: V = [xm, (y0 + y1) / 2, z0];
    this.tri([x0, y0, z0], [x1, y0, z0], [xm, y0, z1], c);
    this.tri([x0, y1, z0], [x1, y1, z0], [xm, y1, z1], c);
    this.quad([x0, y0, z0], [x0, y1, z0], [xm, y1, z1], [xm, y0, z1], c);
    this.quad([x1, y0, z0], [x1, y1, z0], [xm, y1, z1], [xm, y0, z1], c);
    return this;
  }

  // Dente de serra da fábrica: rampa voltada para trás, face reta para a frente.
  dente(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) {
    const c: V = [(x0 + x1) / 2, (y0 + y1) / 2, z0];
    this.quad([x0, y0, z0], [x1, y0, z0], [x1, y1, z1], [x0, y1, z1], c);
    this.quad([x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1], c);
    this.tri([x0, y0, z0], [x0, y1, z0], [x0, y1, z1], c);
    this.tri([x1, y0, z0], [x1, y1, z0], [x1, y1, z1], c);
    return this;
  }

  cilindro(cx: number, cy: number, r: number, z0: number, z1: number, lados = 8) {
    const c: V = [cx, cy, (z0 + z1) / 2];
    const ponto = (i: number, z: number): V => {
      const a = (i / lados) * Math.PI * 2;
      return [cx + Math.cos(a) * r, cy + Math.sin(a) * r, z];
    };
    for (let i = 0; i < lados; i++) {
      this.quad(ponto(i, z0), ponto(i + 1, z0), ponto(i + 1, z1), ponto(i, z1), c);
      this.tri([cx, cy, z1], ponto(i, z1), ponto(i + 1, z1), [cx, cy, z0]);
    }
    return this;
  }

  malha(): Malha {
    return {
      attributes: {
        positions: { value: new Float32Array(this.pos), size: 3 },
        normals: { value: new Float32Array(this.nor), size: 3 },
      },
    };
  }
}

const novo = () => new Construtor();

export interface FormaDeConstrucao {
  corpo: Malha;
  detalhe: Malha;
  corDoDetalhe: [number, number, number];
}

// Alturas em unidades do mundo; o lote tem cerca de 55 × 37.
export const FORMAS: Record<Estilo, FormaDeConstrucao> = {
  casa: {
    corpo: novo().caixa(-0.32, -0.3, 0, 0.32, 0.3, 8).malha(),
    detalhe: novo().duasAguas(-0.36, -0.36, 0.36, 0.36, 8, 15).malha(),
    corDoDetalhe: [176, 84, 60],
  },
  loja: {
    corpo: novo().caixa(-0.4, -0.34, 0, 0.4, 0.3, 9).malha(),
    // Toldo inclinado sobre a calçada da frente.
    detalhe: novo().dente(-0.4, 0.4, 0.3, 0.44, 5, 7).caixa(-0.42, 0.26, 9, 0.42, 0.32, 11).malha(),
    corDoDetalhe: [242, 101, 34],
  },
  shopping: {
    corpo: novo().caixa(-0.47, -0.42, 0, 0.47, 0.34, 11).caixa(-0.44, -0.4, 11, 0.44, 0.3, 13).malha(),
    detalhe: novo().caixa(-0.3, 0.34, 6, 0.3, 0.46, 7).caixa(-0.18, 0.28, 13, 0.18, 0.32, 20).malha(),
    corDoDetalhe: [29, 53, 87],
  },
  fabrica: {
    corpo: novo().caixa(-0.46, -0.34, 0, 0.46, 0.3, 8).malha(),
    detalhe: novo()
      .dente(-0.46, -0.16, -0.34, 0.3, 8, 13)
      .dente(-0.15, 0.15, -0.34, 0.3, 8, 13)
      .dente(0.16, 0.46, -0.34, 0.3, 8, 13)
      .cilindro(0.34, -0.22, 0.05, 8, 26)
      .malha(),
    corDoDetalhe: [128, 128, 132],
  },
  publico: {
    corpo: novo().caixa(-0.44, -0.36, 0, 0.44, 0.34, 1.5).caixa(-0.36, -0.3, 1.5, 0.36, 0.2, 13).malha(),
    detalhe: novo()
      .cilindro(-0.3, 0.27, 0.035, 1.5, 12)
      .cilindro(-0.1, 0.27, 0.035, 1.5, 12)
      .cilindro(0.1, 0.27, 0.035, 1.5, 12)
      .cilindro(0.3, 0.27, 0.035, 1.5, 12)
      .caixa(-0.38, -0.32, 12, 0.38, 0.32, 13.5)
      .frontao(-0.38, 0.38, 0.12, 0.32, 13.5, 19)
      .malha(),
    corDoDetalhe: [244, 242, 236],
  },
  torre: {
    corpo: novo().caixa(-0.24, -0.3, 0, 0.24, 0.3, 46).malha(),
    detalhe: novo().caixa(-0.19, -0.24, 46, 0.19, 0.24, 51).cilindro(0, 0, 0.015, 51, 60, 6).malha(),
    corDoDetalhe: [29, 53, 87],
  },
  tecnico: {
    corpo: novo().caixa(-0.34, -0.3, 0, 0.34, 0.3, 20).malha(),
    detalhe: novo()
      .caixa(-0.2, -0.18, 20, 0.05, 0.12, 23)
      .cilindro(0.2, -0.1, 0.02, 20, 33, 6)
      .cilindro(0.2, -0.1, 0.07, 31, 32, 8)
      .malha(),
    corDoDetalhe: [96, 104, 116],
  },
  escritorio: {
    corpo: novo().caixa(-0.32, -0.28, 0, 0.32, 0.28, 27).malha(),
    // Faixas de janela: lâminas de vidro um pouco salientes.
    detalhe: novo()
      .caixa(-0.33, -0.29, 6, 0.33, 0.29, 9)
      .caixa(-0.33, -0.29, 13, 0.33, 0.29, 16)
      .caixa(-0.33, -0.29, 20, 0.33, 0.29, 23)
      .malha(),
    corDoDetalhe: [70, 92, 116],
  },
  placa: {
    corpo: novo().cilindro(0, 0, 0.02, 0, 16, 6).malha(),
    detalhe: novo().caixa(-0.16, -0.03, 12, 0.16, 0.03, 20).malha(),
    corDoDetalhe: [242, 101, 34],
  },
};

export const ESTILOS = Object.keys(FORMAS) as Estilo[];
