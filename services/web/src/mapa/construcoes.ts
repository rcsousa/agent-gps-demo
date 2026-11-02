// As construções da cidade, montadas em código como malhas 3D. Cada estilo tem três partes,
// desenhadas por três camadas SimpleMeshLayer:
// - o corpo, na cor do bairro;
// - o detalhe (telhado, toldo, colunas, letreiro…), numa cor própria do estilo;
// - o vidro (janelas, vitrines e portas).
// X e Y vão de -0,5 a 0,5 (frações do lote); Z está em unidades do mundo. A frente (a porta) fica em +Y.

import type { Estilo } from '../tipos';

type V = [number, number, number];
type RGB = [number, number, number];

export interface Malha {
  attributes: { positions: { value: Float32Array; size: 3 }; normals: { value: Float32Array; size: 3 } };
}

// Quanto as janelas e portas saltam da fachada (em fração do lote): o bastante para não piscar.
const SALTO = 0.012;

interface OpcoesDeJanela {
  andar: number; // altura de cada andar
  alto: number; // altura da janela
  largo: number; // largura da janela (fração do lote)
  passo: number; // distância entre janelas (fração do lote)
  porta?: number; // meia-largura do vão da porta, no térreo da frente
  terreo?: boolean; // false: o térreo não tem janelas (vitrine, garagem…)
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

  // Frontão (triângulo em pé) ao longo de X.
  frontao(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) {
    const xm = (x0 + x1) / 2;
    const c: V = [xm, (y0 + y1) / 2, z0];
    this.tri([x0, y0, z0], [x1, y0, z0], [xm, y0, z1], c);
    this.tri([x0, y1, z0], [x1, y1, z0], [xm, y1, z1], c);
    this.quad([x0, y0, z0], [x0, y1, z0], [xm, y1, z1], [xm, y0, z1], c);
    this.quad([x1, y0, z0], [x1, y1, z0], [xm, y1, z1], [xm, y0, z1], c);
    return this;
  }

  // Dente de serra: rampa voltada para trás, face reta para a frente.
  dente(x0: number, x1: number, y0: number, y1: number, z0: number, z1: number) {
    const c: V = [(x0 + x1) / 2, (y0 + y1) / 2, z0];
    this.quad([x0, y0, z0], [x1, y0, z0], [x1, y1, z1], [x0, y1, z1], c);
    this.quad([x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1], c);
    this.tri([x0, y0, z0], [x0, y1, z0], [x0, y1, z1], c);
    this.tri([x1, y0, z0], [x1, y1, z0], [x1, y1, z1], c);
    return this;
  }

  cilindro(cx: number, cy: number, r: number, z0: number, z1: number, lados = 8, r1 = r) {
    const c: V = [cx, cy, (z0 + z1) / 2];
    const ponto = (i: number, z: number, raio: number): V => {
      const a = (i / lados) * Math.PI * 2;
      return [cx + Math.cos(a) * raio, cy + Math.sin(a) * raio, z];
    };
    for (let i = 0; i < lados; i++) {
      this.quad(ponto(i, z0, r), ponto(i + 1, z0, r), ponto(i + 1, z1, r1), ponto(i, z1, r1), c);
      if (r1 > 0) this.tri([cx, cy, z1], ponto(i, z1, r1), ponto(i + 1, z1, r1), [cx, cy, z0]);
    }
    return this;
  }

  // Cúpula: anéis de cilindros cada vez mais estreitos.
  cupula(cx: number, cy: number, r: number, z0: number, altura: number) {
    const aneis = 4;
    for (let i = 0; i < aneis; i++) {
      const a0 = (i / aneis) * (Math.PI / 2);
      const a1 = ((i + 1) / aneis) * (Math.PI / 2);
      this.cilindro(cx, cy, r * Math.cos(a0), z0 + altura * Math.sin(a0), z0 + altura * Math.sin(a1), 12, r * Math.cos(a1));
    }
    return this;
  }

  // Janelas nas quatro fachadas de uma caixa, uma fileira por andar.
  janelas(x0: number, y0: number, x1: number, y1: number, z0: number, z1: number, o: OpcoesDeJanela) {
    const colunas = (a: number, b: number) => {
      const n = Math.max(1, Math.floor((b - a) / o.passo));
      const inicio = (a + b) / 2 - ((n - 1) * o.passo) / 2;
      return Array.from({ length: n }, (_, i) => inicio + i * o.passo);
    };
    const meio = o.largo / 2;
    for (let k = 0, zc = z0 + o.andar / 2; zc + o.alto / 2 <= z1 - 0.4; k++, zc += o.andar) {
      if (k === 0 && o.terreo === false) continue;
      const [za, zb] = [zc - o.alto / 2, zc + o.alto / 2];
      for (const x of colunas(x0 + 0.04, x1 - 0.04)) {
        if (!(k === 0 && o.porta && Math.abs(x) < o.porta + meio)) this.caixa(x - meio, y1, za, x + meio, y1 + SALTO, zb);
        this.caixa(x - meio, y0 - SALTO, za, x + meio, y0, zb);
      }
      for (const y of colunas(y0 + 0.04, y1 - 0.04)) {
        this.caixa(x0 - SALTO, y - meio, za, x0, y + meio, zb);
        this.caixa(x1, y - meio, za, x1 + SALTO, y + meio, zb);
      }
    }
    return this;
  }

  // Faixas contínuas de vidro em volta do prédio (escritórios e torres).
  faixas(x0: number, y0: number, x1: number, y1: number, z0: number, z1: number, andar: number, alto: number, desde = 0) {
    for (let z = z0 + desde + (andar - alto) / 2; z + alto <= z1 - 0.4; z += andar)
      this.caixa(x0 - SALTO, y0 - SALTO, z, x1 + SALTO, y1 + SALTO, z + alto);
    return this;
  }

  // Porta na fachada da frente (+Y).
  porta(xc: number, meiaLargura: number, y1: number, altura: number) {
    return this.caixa(xc - meiaLargura, y1, 0, xc + meiaLargura, y1 + SALTO * 1.5, altura);
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
  vidro: Malha;
  corDoDetalhe: RGB;
  paleta?: RGB[]; // detalhe com cor sorteada por construção (os toldos das lojas)
  corDoVidro: RGB;
  altura: [number, number]; // variação da altura entre construções do mesmo estilo
}

const LARANJA: RGB = [242, 101, 34];
const MARINHO: RGB = [29, 53, 87];
const TELHA: RGB = [168, 82, 58];
const PEDRA: RGB = [240, 237, 228];
const VIDRO: RGB = [52, 76, 104];
const VIDRO_CLARO: RGB = [92, 128, 160];
const TOLDOS: RGB[] = [LARANJA, MARINHO, [0, 125, 121], [214, 160, 38], [105, 41, 196], [25, 128, 56]];

// Alturas em unidades do mundo; o lote tem cerca de 42 × 34.
export const FORMAS: Record<Estilo, FormaDeConstrucao> = {
  // --- Cliente e Relacionamento ---------------------------------------------------------
  casa: {
    corpo: novo().caixa(-0.3, -0.26, 0, 0.3, 0.26, 7).malha(),
    detalhe: novo().duasAguas(-0.35, -0.33, 0.35, 0.33, 7, 13).caixa(0.14, -0.12, 9, 0.22, -0.04, 15).malha(),
    vidro: novo()
      .janelas(-0.3, -0.26, 0.3, 0.26, 0, 7, { andar: 7, alto: 2.6, largo: 0.12, passo: 0.24, porta: 0.07 })
      .porta(0, 0.06, 0.26, 4.8)
      .malha(),
    corDoDetalhe: TELHA,
    corDoVidro: VIDRO_CLARO,
    altura: [0.9, 1.1],
  },
  sobrado: {
    corpo: novo().caixa(-0.28, -0.26, 0, 0.28, 0.26, 12).caixa(0.28, -0.2, 0, 0.42, 0.26, 5).malha(),
    detalhe: novo()
      .duasAguas(-0.33, -0.32, 0.33, 0.32, 12, 18)
      .caixa(-0.3, 0.26, 5.6, 0.1, 0.36, 6.2) // sacada
      .caixa(0.3, 0.26, 0.2, 0.4, 0.27, 4) // portão da garagem
      .malha(),
    vidro: novo()
      .janelas(-0.28, -0.26, 0.28, 0.26, 0, 12, { andar: 6, alto: 2.6, largo: 0.12, passo: 0.2, porta: 0.07 })
      .porta(-0.05, 0.06, 0.26, 4.6)
      .malha(),
    corDoDetalhe: TELHA,
    corDoVidro: VIDRO_CLARO,
    altura: [0.95, 1.1],
  },
  residencial: {
    corpo: novo().caixa(-0.3, -0.3, 0, 0.3, 0.3, 26).malha(),
    detalhe: novo()
      .caixa(-0.32, -0.32, 26, 0.32, 0.32, 27.4) // platibanda
      .caixa(-0.24, 0.3, 4.8, -0.04, 0.36, 5.2)
      .caixa(-0.24, 0.3, 9.8, -0.04, 0.36, 10.2)
      .caixa(-0.24, 0.3, 14.8, -0.04, 0.36, 15.2)
      .caixa(-0.24, 0.3, 19.8, -0.04, 0.36, 20.2) // varandas
      .caixa(0.06, 0.3, 4.2, 0.22, 0.38, 4.6) // marquise
      .malha(),
    vidro: novo()
      .janelas(-0.3, -0.3, 0.3, 0.3, 0, 26, { andar: 5, alto: 2.6, largo: 0.09, passo: 0.15, porta: 0.08 })
      .porta(0.14, 0.06, 0.3, 4)
      .malha(),
    corDoDetalhe: PEDRA,
    corDoVidro: VIDRO,
    altura: [0.8, 1.35],
  },
  agencia: {
    corpo: novo().caixa(-0.38, -0.3, 0, 0.38, 0.28, 10).malha(),
    detalhe: novo()
      .caixa(-0.39, 0.28, 7.2, 0.39, 0.32, 9.6) // letreiro do Banco Bússola
      .caixa(-0.16, 0.28, 5.6, 0.16, 0.4, 6) // marquise
      .malha(),
    vidro: novo()
      .caixa(-0.34, 0.28, 0.6, 0.34, 0.28 + SALTO, 5.4) // vitrine
      .janelas(-0.38, -0.3, 0.38, 0.28, 0, 10, { andar: 10, alto: 3.4, largo: 0.12, passo: 0.22, terreo: true, porta: 0.4 })
      .malha(),
    corDoDetalhe: LARANJA,
    corDoVidro: VIDRO,
    altura: [1, 1],
  },
  torre: {
    corpo: novo().caixa(-0.24, -0.28, 0, 0.24, 0.28, 44).caixa(-0.32, -0.34, 0, 0.32, 0.34, 5).malha(),
    detalhe: novo().caixa(-0.2, -0.24, 44, 0.2, 0.24, 48).cilindro(0, 0, 0.012, 48, 58, 6).malha(),
    vidro: novo()
      .faixas(-0.24, -0.28, 0.24, 0.28, 5, 44, 3.2, 2.2)
      .porta(0, 0.1, 0.34, 3.6)
      .malha(),
    corDoDetalhe: MARINHO,
    corDoVidro: VIDRO,
    altura: [0.8, 1.3],
  },
  sede: {
    corpo: novo().caixa(-0.42, -0.36, 0, 0.42, 0.32, 6).caixa(-0.26, -0.24, 6, 0.26, 0.2, 34).malha(),
    detalhe: novo()
      .caixa(-0.27, -0.25, 32, 0.27, 0.21, 34.6) // coroamento laranja da marca
      .caixa(-0.44, -0.38, 6, 0.44, 0.34, 6.8)
      .caixa(-0.2, 0.32, 3.8, 0.2, 0.44, 4.3) // marquise
      .malha(),
    vidro: novo()
      .faixas(-0.26, -0.24, 0.26, 0.2, 6, 32, 3, 2)
      .caixa(-0.38, 0.32, 0.5, 0.38, 0.32 + SALTO, 3.4)
      .malha(),
    corDoDetalhe: LARANJA,
    corDoVidro: VIDRO,
    altura: [0.95, 1.1],
  },

  // --- Regras e Governança --------------------------------------------------------------
  publico: {
    corpo: novo().caixa(-0.44, -0.36, 0, 0.44, 0.34, 1.5).caixa(-0.36, -0.3, 1.5, 0.36, 0.2, 13).malha(),
    detalhe: novo()
      .cilindro(-0.3, 0.27, 0.03, 1.5, 12)
      .cilindro(-0.1, 0.27, 0.03, 1.5, 12)
      .cilindro(0.1, 0.27, 0.03, 1.5, 12)
      .cilindro(0.3, 0.27, 0.03, 1.5, 12)
      .caixa(-0.38, -0.32, 12, 0.38, 0.32, 13.5)
      .frontao(-0.38, 0.38, 0.12, 0.32, 13.5, 19)
      .malha(),
    vidro: novo()
      .janelas(-0.36, -0.3, 0.36, 0.2, 1.5, 13, { andar: 5.5, alto: 3.2, largo: 0.07, passo: 0.2, porta: 0.06 })
      .porta(0, 0.07, 0.2, 7)
      .malha(),
    corDoDetalhe: PEDRA,
    corDoVidro: VIDRO,
    altura: [0.9, 1.1],
  },
  cupula: {
    corpo: novo().caixa(-0.38, -0.32, 0, 0.38, 0.3, 12).cilindro(0, -0.02, 0.15, 12, 16, 12).malha(),
    detalhe: novo()
      .cupula(0, -0.02, 0.15, 16, 8)
      .cilindro(0, -0.02, 0.012, 23.5, 27, 6)
      .caixa(-0.16, 0.3, 0, 0.16, 0.38, 10)
      .frontao(-0.18, 0.18, 0.3, 0.4, 10, 14)
      .malha(),
    vidro: novo()
      .janelas(-0.38, -0.32, 0.38, 0.3, 0, 12, { andar: 6, alto: 3.4, largo: 0.06, passo: 0.14, porta: 0.18 })
      .porta(0, 0.07, 0.38, 6)
      .malha(),
    corDoDetalhe: PEDRA,
    corDoVidro: VIDRO,
    altura: [1, 1.1],
  },
  escritorio: {
    corpo: novo().caixa(-0.32, -0.28, 0, 0.32, 0.28, 22).malha(),
    detalhe: novo()
      .caixa(-0.14, -0.14, 22, 0.1, 0.08, 24.5) // casa de máquinas
      .caixa(-0.12, 0.28, 3.6, 0.12, 0.38, 4) // marquise
      .malha(),
    vidro: novo()
      .faixas(-0.32, -0.28, 0.32, 0.28, 0, 22, 4, 2.4, 4)
      .porta(0, 0.08, 0.28, 3.4)
      .malha(),
    corDoDetalhe: [120, 124, 130],
    corDoVidro: VIDRO,
    altura: [0.7, 1.3],
  },
  central: {
    corpo: novo().caixa(-0.38, -0.32, 0, 0.38, 0.28, 15).malha(),
    detalhe: novo()
      .caixa(-0.42, -0.36, 15, 0.42, 0.36, 16.4) // laje em balanço
      .caixa(-0.3, -0.26, 16.4, -0.02, 0, 17.2)
      .caixa(0.04, -0.26, 16.4, 0.3, 0, 17.2) // painéis solares
      .malha(),
    vidro: novo()
      .caixa(-0.36, 0.28, 0.4, 0.36, 0.28 + SALTO, 14) // pele de vidro na frente
      .faixas(-0.38, -0.32, 0.38, 0.28, 0, 15, 3.8, 2.2)
      .malha(),
    corDoDetalhe: [70, 78, 88],
    corDoVidro: VIDRO,
    altura: [0.95, 1.15],
  },

  // --- Produtos e Ofertas ---------------------------------------------------------------
  loja: {
    corpo: novo().caixa(-0.38, -0.32, 0, 0.38, 0.28, 9).malha(),
    detalhe: novo().dente(-0.38, 0.38, 0.28, 0.42, 4.6, 6.6).caixa(-0.4, 0.26, 9, 0.4, 0.31, 10.6).malha(),
    vidro: novo()
      .caixa(-0.34, 0.28, 0.5, 0.34, 0.28 + SALTO, 4.4) // vitrine
      .janelas(-0.38, -0.32, 0.38, 0.28, 0, 9, { andar: 9, alto: 2.8, largo: 0.1, passo: 0.2, terreo: true, porta: 0.4 })
      .malha(),
    corDoDetalhe: LARANJA,
    paleta: TOLDOS,
    corDoVidro: VIDRO_CLARO,
    altura: [0.85, 1.15],
  },
  galeria: {
    corpo: novo().caixa(-0.4, -0.3, 0, 0.4, 0.22, 15).malha(),
    detalhe: novo()
      .caixa(-0.4, 0.22, 6.2, 0.4, 0.36, 7) // arcada
      .caixa(-0.38, 0.32, 0, -0.34, 0.36, 6.2)
      .caixa(-0.13, 0.32, 0, -0.09, 0.36, 6.2)
      .caixa(0.09, 0.32, 0, 0.13, 0.36, 6.2)
      .caixa(0.34, 0.32, 0, 0.38, 0.36, 6.2)
      .caixa(-0.42, -0.32, 15, 0.42, 0.24, 16) // cornija
      .malha(),
    vidro: novo()
      .caixa(-0.36, 0.22, 0.4, 0.36, 0.22 + SALTO, 5.4)
      .janelas(-0.4, -0.3, 0.4, 0.22, 7, 15, { andar: 4, alto: 2.4, largo: 0.08, passo: 0.16 })
      .malha(),
    corDoDetalhe: LARANJA,
    paleta: TOLDOS,
    corDoVidro: VIDRO,
    altura: [0.9, 1.1],
  },
  shopping: {
    corpo: novo().caixa(-0.47, -0.42, 0, 0.47, 0.32, 12).caixa(-0.44, -0.4, 12, 0.44, 0.28, 14).malha(),
    detalhe: novo()
      .caixa(-0.2, 0.32, 0, 0.2, 0.42, 13) // átrio de entrada
      .caixa(-0.16, 0.38, 13, 0.16, 0.42, 19) // letreiro
      .caixa(-0.47, 0.32, 5.6, 0.47, 0.4, 6.2) // marquise
      .malha(),
    vidro: novo()
      .caixa(-0.17, 0.42, 0.5, 0.17, 0.42 + SALTO, 12)
      .faixas(-0.47, -0.42, 0.47, 0.32, 6.2, 12, 5, 2.4)
      .caixa(-0.45, 0.32, 0.5, -0.22, 0.32 + SALTO, 5)
      .caixa(0.22, 0.32, 0.5, 0.45, 0.32 + SALTO, 5)
      .malha(),
    corDoDetalhe: MARINHO,
    corDoVidro: VIDRO,
    altura: [1, 1.1],
  },

  // --- Serviços e Parceiros -------------------------------------------------------------
  tecnico: {
    corpo: novo().caixa(-0.34, -0.3, 0, 0.34, 0.3, 18).malha(),
    detalhe: novo()
      .caixa(-0.22, -0.2, 18, 0.04, 0.1, 21)
      .cilindro(0.2, -0.1, 0.018, 18, 31, 6)
      .cilindro(0.2, -0.1, 0.07, 29, 30, 8) // antena
      .caixa(-0.1, 0.3, 3.4, 0.1, 0.38, 3.8)
      .malha(),
    vidro: novo()
      .janelas(-0.34, -0.3, 0.34, 0.3, 0, 18, { andar: 4.5, alto: 1.4, largo: 0.18, passo: 0.24, porta: 0.06 })
      .porta(0, 0.06, 0.3, 3.2)
      .malha(),
    corDoDetalhe: [96, 104, 116],
    corDoVidro: VIDRO,
    altura: [0.85, 1.25],
  },
  oficina: {
    corpo: novo().caixa(-0.42, -0.32, 0, 0.42, 0.28, 9).malha(),
    detalhe: novo()
      .duasAguas(-0.44, -0.34, 0.44, 0.3, 9, 13)
      .caixa(-0.3, 0.28, 0.2, 0.02, 0.29, 7) // portão de enrolar
      .caixa(0.08, 0.28, 7.6, 0.38, 0.32, 8.8) // placa
      .malha(),
    vidro: novo()
      .janelas(-0.42, -0.32, 0.42, 0.28, 4, 9, { andar: 5, alto: 1.6, largo: 0.14, passo: 0.2 })
      .porta(0.2, 0.06, 0.28, 4)
      .malha(),
    corDoDetalhe: [128, 128, 132],
    corDoVidro: VIDRO,
    altura: [0.95, 1.05],
  },

  // --- Pagamentos e Emissão -------------------------------------------------------------
  datacenter: {
    corpo: novo().caixa(-0.4, -0.32, 0, 0.4, 0.3, 12).malha(),
    detalhe: (() => {
      const c = novo();
      for (let x = -0.36; x <= 0.36; x += 0.06) c.caixa(x - 0.008, 0.3, 1.5, x + 0.008, 0.33, 11); // grelhas
      return c
        .caixa(-0.3, -0.24, 12, -0.12, -0.06, 14.5)
        .caixa(-0.06, -0.24, 12, 0.12, -0.06, 14.5)
        .caixa(0.18, -0.24, 12, 0.34, -0.06, 14.5) // resfriadores
        .malha();
    })(),
    vidro: novo().porta(-0.3, 0.05, 0.3, 3.4).faixas(-0.4, -0.32, 0.4, 0.3, 0, 12, 12, 0.8, 4).malha(),
    corDoDetalhe: [88, 94, 104],
    corDoVidro: VIDRO,
    altura: [1, 1.1],
  },
  cartorio: {
    corpo: novo().caixa(-0.34, -0.3, 0, 0.34, 0.24, 11).malha(),
    detalhe: novo()
      .caixa(-0.36, 0.24, 0, -0.3, 0.28, 11)
      .caixa(0.3, 0.24, 0, 0.36, 0.28, 11) // pilastras
      .caixa(-0.36, -0.32, 11, 0.36, 0.28, 12)
      .frontao(-0.36, 0.36, 0.1, 0.28, 12, 16)
      .caixa(-0.12, 0.24, 0, 0.12, 0.34, 0.8) // degraus
      .malha(),
    vidro: novo()
      .janelas(-0.34, -0.3, 0.34, 0.24, 0, 11, { andar: 5.5, alto: 3, largo: 0.07, passo: 0.17, porta: 0.06 })
      .porta(0, 0.06, 0.24, 5)
      .malha(),
    corDoDetalhe: PEDRA,
    corDoVidro: VIDRO,
    altura: [0.95, 1.1],
  },

  placa: {
    corpo: novo().cilindro(0, 0, 0.02, 0, 16, 6).malha(),
    detalhe: novo().caixa(-0.16, -0.03, 12, 0.16, 0.03, 20).malha(),
    vidro: novo().malha(),
    corDoDetalhe: LARANJA,
    corDoVidro: VIDRO,
    altura: [1, 1],
  },
};

export const ESTILOS = Object.keys(FORMAS) as Estilo[];
