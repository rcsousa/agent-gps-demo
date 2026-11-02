// As camadas do Modo Mapa. A cidade vem do grafo; o que se move vem dos eventos da viagem.

import type { Layer } from '@deck.gl/core';
import { PathStyleExtension, type PathStyleExtensionProps } from '@deck.gl/extensions';
import { TripsLayer } from '@deck.gl/geo-layers';
import { IconLayer, LineLayer, PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers';

import type { Bairro, Cidade, NoDoMapa, ParadaDaRota, Ponto, RotaDaJornada } from '../tipos';
import { ICONE_CHEGADA, ICONE_ROBO } from './icones';
import type { EstadoDaViagem, Pulso } from './viagem';

type Cor = [number, number, number, number];

const hex = (cor: string, alfa = 255): Cor => [
  parseInt(cor.slice(1, 3), 16),
  parseInt(cor.slice(3, 5), 16),
  parseInt(cor.slice(5, 7), 16),
  alfa,
];

// Semáforo dessaturado: nunca sozinho (o status também aparece por ícone e no painel).
export const COR_STATUS: Record<string, Cor> = {
  ok: [74, 156, 108, 255],
  degradado: [214, 158, 56, 255],
  fora: [208, 76, 76, 255],
};
export const SIMBOLO_STATUS: Record<string, string> = { degradado: '!', fora: '✕' };
const LARANJA: Cor = [242, 101, 34, 255];
const TEXTO: Cor = [32, 32, 32, 255];

// Nível de zoom relativo ao enquadramento inicial: decide o que aparece (zoom semântico).
export const DURACAO_DO_PULSO_MS = 1200;
export const NIVEL = { arestas: 0.6, nomes: 1.1, rotulosDeAresta: 2.0, bairrosSomem: 2.2 };

export interface Contexto {
  cidade: Cidade;
  rotas: RotaDaJornada[];
  viagem: EstadoDaViagem;
  nivel: number; // zoom atual menos o zoom de enquadramento
  tempo: number; // segundos, para as animações
  agora: number; // performance.now(), para os pulsos
  destacada: string | null; // rota com o mouse em cima, no cartão de rotas
  posicaoDoRobo: Ponto | null;
  nomesVisiveis: NoDoMapa[]; // de rotulosQueCabem, calculado só quando o zoom muda
}

// Declutter simples em pixels: os nomes entram por prioridade (paradas, nós com status, demais)
// e só ficam os que não encostam em nenhum já colocado.
export function rotulosQueCabem(nos: NoDoMapa[], zoom: number): NoDoMapa[] {
  const escala = 2 ** zoom;
  const prioridade = (n: NoDoMapa) => (n.tipo === 'Parada' ? 0 : n.status && n.status !== 'ok' ? 1 : 2);
  const colocados: [number, number, number, number][] = [];
  const visiveis: NoDoMapa[] = [];
  for (const n of [...nos].sort((a, b) => prioridade(a) - prioridade(b))) {
    const largura = n.nome.length * 6.8 + 6;
    const x = n.x * escala - largura / 2;
    const y = n.y * escala + (n.tipo === 'Parada' ? 22 : 14) - 7;
    const caixa: [number, number, number, number] = [x, y, x + largura, y + 14];
    if (colocados.some((o) => caixa[0] < o[2] && caixa[2] > o[0] && caixa[1] < o[3] && caixa[3] > o[1])) continue;
    colocados.push(caixa);
    visiveis.push(n);
  }
  return visiveis;
}

const centro = (pontos: Ponto[]): Ponto => [
  pontos.reduce((s, p) => s + p[0], 0) / pontos.length,
  pontos.reduce((s, p) => s + p[1], 0) / pontos.length,
];

function posicoes(cidade: Cidade): Map<string, NoDoMapa> {
  return new Map(cidade.nos.map((n) => [n.id, n]));
}

// As rotas compartilham paradas: um pequeno deslocamento separa as linhas no mapa.
const DESLOCAMENTO: Record<string, number> = { 'rota-rapida': -5, 'rota-economica': 0, 'rota-assistida': 5 };

export function caminhoDaRota(rota: RotaDaJornada, nos: Map<string, NoDoMapa>): Ponto[] {
  const d = DESLOCAMENTO[rota.id] ?? 0;
  return rota.paradas
    .map((p) => nos.get(p.id))
    .filter((n): n is NoDoMapa => Boolean(n))
    .map((n) => [n.x + d, n.y + d] as Ponto);
}

export function camadas(c: Contexto) {
  const { cidade, viagem, nivel } = c;
  const nos = posicoes(cidade);
  const corDoBairro = new Map(cidade.bairros.map((b) => [b.id, b.cor]));
  const centros = new Map(cidade.bairros.map((b) => [b.id, centro(b.poligono)]));
  const paradasNumeradas =
    (c.rotas.find((r) => r.id === (viagem.rota || 'rota-economica')) ?? c.rotas[0])?.paradas ?? [];

  const lista: Layer[] = [
    new PolygonLayer<Bairro>({
      id: 'bairros',
      data: cidade.bairros,
      getPolygon: (b) => b.poligono,
      getFillColor: (b): Cor => hex(b.cor, 34),
      getLineColor: (b): Cor => hex(b.cor, 140),
      lineWidthUnits: 'pixels',
      getLineWidth: 2,
    }),
    new PathLayer<{ caminho: Ponto[] }>({
      id: 'rio',
      data: [{ caminho: cidade.rio }],
      getPath: (d) => d.caminho,
      getColor: [120, 170, 215, 200],
      getWidth: 16,
      widthUnits: 'common',
      capRounded: true,
      jointRounded: true,
    }),
    new LineLayer<Cidade['avenidas'][number]>({
      id: 'avenidas',
      data: cidade.avenidas.filter((a) => centros.has(a.de) && centros.has(a.para)),
      getSourcePosition: (a) => centros.get(a.de)!,
      getTargetPosition: (a) => centros.get(a.para)!,
      getColor: [196, 186, 166, 170],
      getWidth: (a) => Math.min(2 + a.relacoes / 3, 10),
      widthUnits: 'pixels',
    }),
    new LineLayer<Cidade['arestas'][number]>({
      id: 'arestas',
      data: cidade.arestas.filter((a) => nos.has(a.de) && nos.has(a.para)),
      visible: nivel >= NIVEL.arestas,
      getSourcePosition: (a) => [nos.get(a.de)!.x, nos.get(a.de)!.y],
      getTargetPosition: (a) => [nos.get(a.para)!.x, nos.get(a.para)!.y],
      getColor: [110, 120, 130, 70],
      getWidth: 1,
      widthUnits: 'pixels',
    }),
    // Rotas disponíveis: tracejadas; a interditada em vermelho; a da viagem, grossa e laranja.
    new PathLayer<RotaDaJornada, PathStyleExtensionProps<RotaDaJornada>>({
      id: 'rotas',
      data: c.rotas,
      getPath: (r) => caminhoDaRota(r, nos),
      getColor: (r): Cor =>
        r.estimativa.bloqueada
          ? COR_STATUS.fora
          : r.id === viagem.rota
            ? LARANJA
            : r.id === c.destacada
              ? [60, 60, 60, 230]
              : [90, 90, 90, 150],
      getWidth: (r) => (r.id === viagem.rota ? 6 : r.id === c.destacada ? 4 : 2.5),
      widthUnits: 'pixels',
      jointRounded: true,
      capRounded: true,
      getDashArray: (r: RotaDaJornada): [number, number] => (r.id === viagem.rota ? [0, 0] : [6, 4]),
      dashJustified: true,
      extensions: [new PathStyleExtension({ dash: true })],
      updateTriggers: {
        getColor: [viagem.rota, c.destacada],
        getWidth: [viagem.rota, c.destacada],
        getDashArray: [viagem.rota],
      },
      transitions: { getWidth: 400 },
    }),
  ];

  // A rota da viagem ganha um rastro animado (só depois do route.planned).
  const rotaAtiva = c.rotas.find((r) => r.id === viagem.rota);
  if (rotaAtiva) {
    const caminho = caminhoDaRota(rotaAtiva, nos);
    const duracao = caminho.length + 2;
    lista.push(
      new TripsLayer<{ caminho: Ponto[]; tempos: number[] }>({
        id: 'rastro',
        data: [{ caminho, tempos: caminho.map((_, i) => i) }],
        getPath: (d) => d.caminho,
        getTimestamps: (d) => d.tempos,
        getColor: [255, 196, 140],
        widthUnits: 'pixels',
        getWidth: 5,
        trailLength: 2.5,
        currentTime: (c.tempo * 2) % duracao,
        capRounded: true,
        jointRounded: true,
      }) as never,
    );
  }

  const visitadas = new Set(viagem.visitadas);
  const comStatus = cidade.nos.filter((n) => n.status === 'degradado' || n.status === 'fora');
  const marcados = new Set(viagem.incidentes.map((i) => i.entidade).filter((e): e is string => Boolean(e)));

  lista.push(
    new ScatterplotLayer<NoDoMapa>({
      id: 'nos',
      data: cidade.nos,
      getPosition: (n) => [n.x, n.y],
      getRadius: (n) => (n.tipo === 'Parada' ? 0 : n.status ? 6 : 4),
      radiusUnits: 'common',
      radiusMinPixels: 2.5,
      getFillColor: (n): Cor => (n.status ? COR_STATUS[n.status] : hex(corDoBairro.get(n.bairro) ?? '#888888', 220)),
      getLineColor: [255, 255, 255, 230],
      lineWidthMinPixels: 1,
      stroked: true,
      pickable: true,
      updateTriggers: { getFillColor: [cidade.nos.map((n) => n.status).join()] },
      transitions: { getFillColor: 400 },
    }),
    new TextLayer<NoDoMapa>({
      id: 'simbolos-de-status',
      data: comStatus,
      getPosition: (n) => [n.x, n.y],
      getText: (n) => SIMBOLO_STATUS[n.status ?? ''] ?? '',
      getSize: 13,
      getColor: [255, 255, 255, 255],
      fontWeight: 700,
      characterSet: 'auto',
      getPixelOffset: [0, 0],
    }),
    new ScatterplotLayer<NoDoMapa>({
      id: 'incidentes',
      data: cidade.nos.filter((n) => marcados.has(n.id)),
      getPosition: (n) => [n.x, n.y],
      getRadius: 14,
      radiusUnits: 'common',
      filled: false,
      stroked: true,
      getLineColor: COR_STATUS.fora,
      lineWidthMinPixels: 3,
    }),
    // Pulso no sistema chamado a cada tool.called (some em 1,2 s).
    new ScatterplotLayer<Pulso>({
      id: 'pulsos',
      data: viagem.pulsos.filter((p) => c.agora - p.quando < DURACAO_DO_PULSO_MS && nos.has(p.no)),
      getPosition: (p) => [nos.get(p.no)!.x, nos.get(p.no)!.y],
      getRadius: (p) => 6 + ((c.agora - p.quando) / DURACAO_DO_PULSO_MS) * 22,
      radiusUnits: 'common',
      filled: false,
      stroked: true,
      getLineColor: (p): Cor => {
        const alfa = 255 * (1 - (c.agora - p.quando) / DURACAO_DO_PULSO_MS);
        return p.ok ? [242, 101, 34, alfa] : [208, 76, 76, alfa];
      },
      lineWidthMinPixels: 2,
      updateTriggers: { getRadius: [c.agora], getLineColor: [c.agora] },
    }),
    // As paradas da jornada: marcadores numerados; as visitadas ficam laranja.
    new ScatterplotLayer<ParadaDaRota>({
      id: 'paradas',
      data: paradasNumeradas.filter((p) => nos.has(p.id)),
      getPosition: (p) => [nos.get(p.id)!.x, nos.get(p.id)!.y],
      getRadius: (p) => (p.id === viagem.parada ? 13 : 10),
      radiusUnits: 'common',
      radiusMinPixels: 8,
      radiusMaxPixels: 16,
      getFillColor: (p): Cor => (visitadas.has(p.id) ? LARANJA : [255, 255, 255, 255]),
      getLineColor: LARANJA,
      lineWidthMinPixels: 2,
      stroked: true,
      pickable: true,
      updateTriggers: { getFillColor: [viagem.visitadas.join()], getRadius: [viagem.parada] },
      transitions: { getRadius: 300 },
    }),
    new TextLayer<ParadaDaRota>({
      id: 'numeros-das-paradas',
      data: paradasNumeradas.filter((p) => nos.has(p.id) && p.numero),
      getPosition: (p) => [nos.get(p.id)!.x, nos.get(p.id)!.y],
      getText: (p) => String(p.numero),
      getSize: 12,
      fontWeight: 700,
      getColor: (p): Cor => (visitadas.has(p.id) ? [255, 255, 255, 255] : LARANJA),
      updateTriggers: { getColor: [viagem.visitadas.join()] },
    }),
    new TextLayer<Bairro>({
      id: 'bairros-nomes',
      data: cidade.bairros,
      visible: nivel < NIVEL.bairrosSomem,
      getPosition: (b) => centro(b.poligono),
      getText: (b) => b.nome.toUpperCase(),
      getSize: 20,
      fontWeight: 700,
      getColor: (b): Cor => hex(b.cor, 200),
      characterSet: 'auto',
      fontFamily: 'IBM Plex Sans, sans-serif',
      outlineWidth: 4,
      outlineColor: [255, 255, 255, 220],
      fontSettings: { sdf: true },
    }),
    // Só os nomes que cabem sem sobrepor (ver rotulosQueCabem).
    new TextLayer<NoDoMapa>({
      id: 'nomes-dos-nos',
      data: c.nomesVisiveis,
      visible: nivel >= NIVEL.nomes,
      getPosition: (n) => [n.x, n.y],
      getText: (n) => n.nome,
      getSize: 12,
      fontWeight: 500,
      getColor: TEXTO,
      getPixelOffset: (n) => [0, n.tipo === 'Parada' ? 22 : 14],

      characterSet: 'auto',
      fontFamily: 'IBM Plex Sans, sans-serif',
      outlineWidth: 3,
      outlineColor: [255, 255, 255, 230],
      fontSettings: { sdf: true },
    }),
    new TextLayer<Cidade['arestas'][number]>({
      id: 'rotulos-das-arestas',
      data: cidade.arestas.filter((a) => nos.has(a.de) && nos.has(a.para)),
      visible: nivel >= NIVEL.rotulosDeAresta,
      getPosition: (a) => [(nos.get(a.de)!.x + nos.get(a.para)!.x) / 2, (nos.get(a.de)!.y + nos.get(a.para)!.y) / 2],
      getText: (a) => a.tipo.replaceAll('_', ' ').toLowerCase(),
      getSize: 9,
      getColor: [90, 90, 90, 220],
      characterSet: 'auto',
      fontFamily: 'IBM Plex Mono, monospace',
    }),
  );

  if (viagem.pedagio && nos.has('parada-aprovacao-humana')) {
    const n = nos.get('parada-aprovacao-humana')!;
    lista.push(
      new TextLayer<NoDoMapa>({
        id: 'pedagio',
        data: [n],
        getPosition: (p) => [p.x, p.y],
        getText: () => 'Pedágio: especialista',
        getSize: 12,
        getPixelOffset: [0, -26],
        background: true,
        getBackgroundColor: [214, 158, 56, 240],
        backgroundPadding: [6, 3],
        getColor: [32, 32, 32, 255],
        characterSet: 'auto',
        fontFamily: 'IBM Plex Sans, sans-serif',
      }),
    );
  }

  const ultima = paradasNumeradas.at(-1);
  if (viagem.fim?.apolice && ultima && nos.has(ultima.id)) {
    const n = nos.get(ultima.id)!;
    lista.push(
      new IconLayer<NoDoMapa>({
        id: 'chegada',
        data: [n],
        getPosition: (p) => [p.x + 14, p.y],
        getIcon: () => ICONE_CHEGADA,
        getSize: 44,
        sizeUnits: 'pixels',
      }),
      new TextLayer<NoDoMapa>({
        id: 'apolice',
        data: [n],
        getPosition: (p) => [p.x + 14, p.y],
        getText: () => `Apólice ${viagem.fim?.apolice}`,
        getSize: 13,
        getPixelOffset: [0, -54],
        background: true,
        getBackgroundColor: [255, 255, 255, 245],
        backgroundPadding: [8, 4],
        getColor: TEXTO,
        characterSet: 'auto',
        fontFamily: 'IBM Plex Sans, sans-serif',
      }),
    );
  }

  if (c.posicaoDoRobo) {
    lista.push(
      new IconLayer<{ posicao: Ponto }>({
        id: 'robo',
        data: [{ posicao: c.posicaoDoRobo }],
        getPosition: (d) => d.posicao,
        getIcon: () => ICONE_ROBO,
        getSize: 56,
        sizeUnits: 'pixels',
        transitions: { getPosition: 600 },
        updateTriggers: { getPosition: [c.posicaoDoRobo.join()] },
      }),
    );
  }
  return lista;
}
