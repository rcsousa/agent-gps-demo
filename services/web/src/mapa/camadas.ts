// As camadas do Modo Mapa: a cidade em grade (ruas, quadras e uma construção por lugar do grafo)
// e o que se move, vindo só dos eventos exibidos pelo diretor de animações: o robô andando
// pelas ruas, o rastro do caminho real, os pulsos nos prédios chamados e os faróis de incidente.

import type { Layer } from '@deck.gl/core';
import { PathStyleExtension, type PathStyleExtensionProps } from '@deck.gl/extensions';
import { TripsLayer } from '@deck.gl/geo-layers';
import {
  ArcLayer,
  ColumnLayer,
  IconLayer,
  LineLayer,
  PathLayer,
  ScatterplotLayer,
  SolidPolygonLayer,
} from '@deck.gl/layers';
import { SimpleMeshLayer } from '@deck.gl/mesh-layers';

import type { Cidade, Estilo, NoDoMapa, ParadaDaRota, RotaDaJornada } from '../tipos';
import {
  type Cena3D,
  type Construcao,
  type Cor,
  misturar,
  type Ponto3,
  type Retangulo3,
  Z_CALCADA,
  Z_CHAO,
  Z_RUA,
} from './cidade3d';
import { ESTILOS, FORMAS } from './construcoes';
import { ICONE_CHEGADA, ICONE_ROBO } from './icones';
import type { EstadoDaViagem, Pulso } from './viagem';

// Semáforo dessaturado: nunca sozinho (o status também aparece por ícone nos rótulos e no painel).
export const COR_STATUS: Record<string, Cor> = {
  ok: [74, 156, 108, 255],
  degradado: [214, 158, 56, 255],
  fora: [208, 76, 76, 255],
};
export const LARANJA: Cor = [242, 101, 34, 255];
export const DURACAO_DO_PULSO_MS = 1400;
export const ALTURA_DO_ROBO = 22; // o pino flutua um pouco acima da rua
const MATERIAL = { ambient: 0.5, diffuse: 0.6, shininess: 24, specularColor: [40, 40, 40] as [number, number, number] };
const Z_ROBO = Z_RUA + 0.3;

// Trânsito é infraestrutura (sistemas, APIs, filas, canais, regras). O estado de um dado de
// cliente (um consentimento revogado, por exemplo) aparece só no painel, nunca como farol.
const DADOS_DE_CLIENTE = new Set(['Cliente', 'Consentimento', 'Conta', 'Imovel', 'ProdutoContratado', 'Relacionamento']);
export const comProblemaNoTransito = (cidade: Cidade) =>
  cidade.nos.filter((n) => (n.status === 'fora' || n.status === 'degradado') && !DADOS_DE_CLIENTE.has(n.tipo));

export function paradasDaJornada(rotas: RotaDaJornada[], rotaAtiva: string | null): ParadaDaRota[] {
  return (rotas.find((r) => r.id === (rotaAtiva || 'rota-economica')) ?? rotas[0])?.paradas ?? [];
}

export interface Rastro {
  pontos: Ponto3[];
  tempos: number[]; // distância acumulada até cada ponto
  percorrido: number; // até onde o robô já foi
}

export interface Contexto {
  cena: Cena3D;
  cidade: Cidade; // o estado vivo (status dos nós)
  exibido: EstadoDaViagem;
  agora: number; // performance.now()
  raioX: boolean;
  selecionado: string | null;
  robo: Ponto3 | null;
  rastro: Rastro | null;
  chegada: Ponto3 | null; // onde a apólice saiu
}

function construcoesDoEstilo(c: Contexto, estilo: Estilo): Layer[] {
  const forma = FORMAS[estilo];
  const dados = c.cena.construcoes.filter((x) => x.estilo === estilo);
  if (!dados.length) return [];
  const visitadas = new Set(c.exibido.visitadas);
  const corDoCorpo = (x: Construcao): Cor =>
    x.no.id === c.selecionado ? misturar(LARANJA, [255, 255, 255, 255], 0.2) : x.cor;
  const corDoDetalhe = (x: Construcao): Cor => {
    if (estilo !== 'placa') return [...forma.corDoDetalhe, 255];
    if (x.no.id === c.exibido.parada) return [214, 80, 20, 255];
    return visitadas.has(x.no.id) ? LARANJA : [250, 248, 244, 255];
  };
  const comum = {
    data: dados,
    getPosition: (x: Construcao) => x.posicao,
    getScale: (x: Construcao) => x.escala,
    getOrientation: (x: Construcao): [number, number, number] => [0, x.yaw, 0],
    material: MATERIAL,
  };
  return [
    new SimpleMeshLayer<Construcao>({
      ...comum,
      id: `construcao-${estilo}`,
      mesh: forma.corpo,
      getColor: corDoCorpo,
      pickable: true,
      updateTriggers: { getColor: [c.selecionado] },
    }),
    new SimpleMeshLayer<Construcao>({
      ...comum,
      id: `detalhe-${estilo}`,
      mesh: forma.detalhe,
      getColor: corDoDetalhe,
      pickable: true,
      updateTriggers: { getColor: [c.exibido.parada, c.exibido.visitadas.join()] },
    }),
  ];
}

export function camadas(c: Contexto): Layer[] {
  const { cena, cidade, exibido } = c;
  const { largura, altura } = cena.mundo;
  const vivos = new Map(cidade.nos.map((n) => [n.id, n]));
  const naCena = (id: string, z = Z_CHAO): Ponto3 | null => {
    const n = vivos.get(id);
    return n ? cena.ponto(n.x, n.y, z) : null;
  };

  const lista: Layer[] = [
    new SolidPolygonLayer<{ poligono: Ponto3[] }>({
      id: 'chao',
      data: [
        {
          poligono: [
            [-60, -60, 0],
            [largura + 60, -60, 0],
            [largura + 60, altura + 60, 0],
            [-60, altura + 60, 0],
          ],
        },
      ],
      getPolygon: (d) => d.poligono,
      getFillColor: [214, 210, 196, 255],
    }),
    new PathLayer<{ caminho: Ponto3[] }>({
      id: 'rio',
      data: [{ caminho: cena.rio }],
      getPath: (d) => d.caminho,
      getColor: [120, 176, 222, 255],
      getWidth: 46,
      widthUnits: 'common',
      jointRounded: true,
      capRounded: true,
    }),
    new SolidPolygonLayer<Retangulo3>({
      id: 'agua',
      data: cena.agua,
      getPolygon: (r) => r.poligono,
      getFillColor: (r) => r.cor,
    }),
    // As ruas passam por cima do rio: são as pontes.
    new SolidPolygonLayer<Retangulo3>({
      id: 'ruas',
      data: cena.ruas,
      getPolygon: (r) => r.poligono,
      getFillColor: (r) => r.cor,
    }),
    new PathLayer<Cena3D['faixas'][number], PathStyleExtensionProps<Cena3D['faixas'][number]>>({
      id: 'faixas',
      data: cena.faixas,
      getPath: (f) => f.caminho,
      getColor: (f): Cor => (f.avenida ? [246, 214, 92, 230] : [255, 255, 255, 170]),
      getWidth: (f) => (f.avenida ? 1.6 : 1),
      widthUnits: 'pixels',
      getDashArray: [4, 4],
      extensions: [new PathStyleExtension({ dash: true })],
    }),
    new SolidPolygonLayer<Retangulo3>({
      id: 'calcadas',
      data: cena.calcadas,
      getPolygon: (r) => r.poligono,
      extruded: true,
      getElevation: Z_CALCADA,
      getFillColor: (r) => r.cor,
      material: MATERIAL,
    }),
    new SolidPolygonLayer<Retangulo3>({
      id: 'lotes',
      data: cena.lotes,
      getPolygon: (r) => r.poligono,
      getFillColor: (r) => r.cor,
    }),
    new ColumnLayer<Ponto3>({
      id: 'troncos',
      data: cena.arvores,
      getPosition: (p) => p,
      diskResolution: 6,
      radius: 0.8,
      getElevation: 4,
      extruded: true,
      getFillColor: [120, 92, 64, 255],
    }),
    new ColumnLayer<Ponto3>({
      id: 'copas',
      data: cena.arvores,
      getPosition: ([x, y, z]) => [x, y, z + 4],
      diskResolution: 8,
      radius: 3.6,
      getElevation: 6,
      extruded: true,
      getFillColor: [92, 146, 86, 255],
      material: MATERIAL,
    }),
    ...ESTILOS.flatMap((estilo) => construcoesDoEstilo(c, estilo)),
  ];

  // Status no chão, em volta de cada lugar que tem estado vivo (sistemas, APIs, filas…).
  const comStatus = cidade.nos.filter((n) => n.status && n.estilo && n.estilo !== 'placa');
  lista.push(
    new ScatterplotLayer<NoDoMapa>({
      id: 'status',
      data: comStatus,
      getPosition: (n) => cena.ponto(n.x, n.y, Z_CHAO + 0.1),
      getRadius: 15,
      radiusUnits: 'common',
      filled: false,
      stroked: true,
      getLineColor: (n): Cor => {
        const [r, g, b] = COR_STATUS[n.status ?? 'ok'];
        return [r, g, b, n.status === 'ok' ? 110 : 255];
      },
      lineWidthMinPixels: 2,
      updateTriggers: { getLineColor: [comStatus.map((n) => n.status).join()] },
    }),
  );

  // Faróis de incidente: visíveis da cidade inteira.
  const comProblema = comProblemaNoTransito(cidade);
  lista.push(
    new ColumnLayer<NoDoMapa>({
      id: 'farois',
      data: comProblema,
      getPosition: (n) => cena.ponto(n.x, n.y, Z_CHAO),
      diskResolution: 8,
      radius: 2.2,
      getElevation: 75,
      extruded: true,
      getFillColor: (n): Cor => {
        const [r, g, b] = COR_STATUS[n.status ?? 'fora'];
        return [r, g, b, 215];
      },
      updateTriggers: { getFillColor: [comProblema.map((n) => n.status).join()] },
    }),
  );

  // Raio-X: o grafo por cima da cidade, em arcos finos entre as construções.
  if (c.raioX) {
    const lugares = new Set(cena.construcoes.map((x) => x.no.id));
    lista.push(
      new ArcLayer<Cidade['arestas'][number]>({
        id: 'relacoes',
        data: cidade.arestas.filter((a) => lugares.has(a.de) && lugares.has(a.para)),
        getSourcePosition: (a) => naCena(a.de, Z_CHAO + 6)!,
        getTargetPosition: (a) => naCena(a.para, Z_CHAO + 6)!,
        getSourceColor: [29, 53, 87, 120],
        getTargetColor: [242, 101, 34, 120],
        getWidth: 1,
        getHeight: 0.25,
        pickable: true,
      }),
    );
  }

  // O caminho real do robô: acende em laranja até onde ele já andou.
  if (c.rastro && c.rastro.pontos.length > 1) {
    const r = c.rastro;
    lista.push(
      new TripsLayer<Rastro>({
        id: 'rastro',
        data: [r],
        getPath: (d) => d.pontos,
        getTimestamps: (d) => d.tempos,
        currentTime: r.percorrido,
        trailLength: 1e7,
        fadeTrail: false,
        getColor: LARANJA,
        getWidth: 6,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
    );
  }

  // Pulsos: o agente chama um sistema (tool.called).
  const recentes = exibido.pulsos.filter((p) => c.agora - p.quando < DURACAO_DO_PULSO_MS && vivos.has(p.no));
  const idade = (p: Pulso) => (c.agora - p.quando) / DURACAO_DO_PULSO_MS;
  lista.push(
    new ScatterplotLayer<Pulso>({
      id: 'pulsos',
      data: recentes,
      getPosition: (p) => naCena(p.no, Z_CHAO + 0.2)!,
      getRadius: (p) => 10 + idade(p) * 26,
      radiusUnits: 'common',
      filled: false,
      stroked: true,
      getLineColor: (p): Cor => (p.ok ? [242, 101, 34, 255 * (1 - idade(p))] : [208, 76, 76, 255 * (1 - idade(p))]),
      lineWidthMinPixels: 3,
      updateTriggers: { getRadius: [c.agora], getLineColor: [c.agora] },
    }),
  );

  if (c.chegada) {
    lista.push(
      new IconLayer<Ponto3>({
        id: 'chegada',
        data: [[c.chegada[0] + 14, c.chegada[1], c.chegada[2]]],
        getPosition: (p) => p,
        getIcon: () => ICONE_CHEGADA,
        getSize: 60,
        sizeUnits: 'pixels',
        parameters: { depthCompare: 'always' },
      }),
    );
  }

  if (c.robo) {
    const [x, y] = c.robo;
    lista.push(
      new ScatterplotLayer<Ponto3>({
        id: 'sombra-do-robo',
        data: [[x, y, Z_ROBO]],
        getPosition: (p) => p,
        getRadius: 5,
        radiusUnits: 'common',
        getFillColor: [0, 0, 0, 80],
      }),
      new LineLayer<Ponto3>({
        id: 'fio-do-robo',
        data: [c.robo],
        getSourcePosition: () => [x, y, Z_ROBO],
        getTargetPosition: () => [x, y, Z_ROBO + ALTURA_DO_ROBO],
        getColor: [29, 53, 87, 140],
        getWidth: 2,
        widthUnits: 'pixels',
      }),
      // O robô é sempre desenhado por cima: nunca some atrás de um prédio.
      new IconLayer<Ponto3>({
        id: 'robo',
        data: [c.robo],
        getPosition: () => [x, y, Z_ROBO + ALTURA_DO_ROBO],
        getIcon: () => ICONE_ROBO,
        getSize: 72,
        sizeUnits: 'pixels',
        parameters: { depthCompare: 'always' },
        updateTriggers: { getPosition: [x, y] },
      }),
    );
  }

  return lista;
}
