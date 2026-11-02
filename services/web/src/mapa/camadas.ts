// As camadas do Modo Mapa em 3D. A cidade vem do grafo; o que se move vem dos eventos exibidos
// pelo diretor de animações. Dois níveis: a cidade inteira e um bairro aberto, com seus sistemas.

import type { Layer } from '@deck.gl/core';
import { PathStyleExtension, type PathStyleExtensionProps } from '@deck.gl/extensions';
import { TripsLayer } from '@deck.gl/geo-layers';
import { ArcLayer, ColumnLayer, IconLayer, LineLayer, PathLayer, ScatterplotLayer, SolidPolygonLayer } from '@deck.gl/layers';

import type { Cidade, NoDoMapa, ParadaDaRota, RotaDaJornada } from '../tipos';
import {
  ALTURA_DA_PLACA,
  alturaDoSistema,
  type BairroCena,
  type Caminho,
  type Cena3D,
  type Cor,
  corDoSistema,
  misturar,
  octogono,
  pegada,
  type Ponto3,
  type Predio,
} from './cidade3d';
import { ICONE_CHEGADA, ICONE_ROBO } from './icones';
import type { EstadoDaViagem, Pulso } from './viagem';

// Semáforo dessaturado: nunca sozinho (o status também aparece por ícone nos rótulos e no painel).
export const COR_STATUS: Record<string, Cor> = {
  ok: [74, 156, 108, 255],
  degradado: [214, 158, 56, 255],
  fora: [208, 76, 76, 255],
};
export const LARANJA: Cor = [242, 101, 34, 255];
const LARANJA_CLARO: Cor = [248, 178, 132, 255];
const CINZA: Cor = [168, 168, 164, 255];
const CHAO: Cor = [226, 220, 205, 255];
const AGUA: Cor = [120, 176, 222, 255];
const MARGEM: Cor = [196, 222, 236, 255];
const PISTA: Cor = [214, 208, 196, 255];
export const DURACAO_DO_PULSO_MS = 1400;

const MATERIAL = { ambient: 0.55, diffuse: 0.55, shininess: 28, specularColor: [40, 40, 40] as [number, number, number] };
const TIPOS_SEM_PREDIO = new Set(['Parada', 'Rota', 'Jornada']);
const Z_ESTRADA = ALTURA_DA_PLACA + 0.6;
export const ALTURA_DO_ROBO = 34; // acima do marco da parada atual (30)

export interface Robo {
  posicao: Ponto3;
  arco: number | null; // posição ao longo da rota ativa (para o rastro), se estiver nela
}

export interface Contexto {
  cena: Cena3D;
  cidade: Cidade; // o estado vivo (status dos nós)
  rotas: RotaDaJornada[];
  caminhos: Map<string, Caminho>;
  exibido: EstadoDaViagem;
  agora: number; // performance.now()
  bairroAberto: string | null;
  raioX: boolean; // no Raio-X, a cidade é o grafo: todos os nós e todas as arestas
  destacada: string | null;
  selecionado: string | null;
  robo: Robo | null;
}

// Trânsito é infraestrutura (sistemas, APIs, filas, canais, regras). O estado de um dado de
// cliente (um consentimento revogado, por exemplo) aparece só dentro do bairro, nunca como farol.
const DADOS_DE_CLIENTE = new Set(['Cliente', 'Consentimento', 'Conta', 'Imovel', 'ProdutoContratado', 'Relacionamento']);
export const comProblemaNoTransito = (cidade: Cidade) =>
  cidade.nos.filter((n) => (n.status === 'fora' || n.status === 'degradado') && !DADOS_DE_CLIENTE.has(n.tipo));

export function paradasDaJornada(rotas: RotaDaJornada[], rotaAtiva: string | null): ParadaDaRota[] {
  return (rotas.find((r) => r.id === (rotaAtiva || 'rota-economica')) ?? rotas[0])?.paradas ?? [];
}

// Nós do bairro aberto que viram prédios-sistema.
export const sistemasDoBairro = (cidade: Cidade, bairro: string | null) =>
  bairro ? cidade.nos.filter((n) => n.bairro === bairro && !TIPOS_SEM_PREDIO.has(n.tipo)) : [];

export function camadas(c: Contexto): Layer[] {
  const { cena, cidade, exibido, bairroAberto } = c;
  const { largura, altura } = cena.mundo;
  const aberto = (id: string) => !bairroAberto || id === bairroAberto;
  const nosVivos = new Map(cidade.nos.map((n) => [n.id, n]));
  const bairroPorId = new Map(cena.bairros.map((b) => [b.id, b]));
  const { raioX } = c;
  const sistemas = raioX
    ? cidade.nos.filter((n) => !TIPOS_SEM_PREDIO.has(n.tipo))
    : sistemasDoBairro(cidade, bairroAberto);
  // No Raio-X, fora do bairro aberto, os nós ficam baixos: dá para ver a cidade inteira como grafo.
  const alturaDoNo = (n: NoDoMapa) => alturaDoSistema(n) * (raioX && n.bairro !== bairroAberto ? 0.4 : 1);
  const noNaCena = (id: string, z = ALTURA_DA_PLACA): Ponto3 | null => {
    const n = nosVivos.get(id);
    return n ? cena.ponto(n.x, n.y, z) : null;
  };

  const lista: Layer[] = [
    new SolidPolygonLayer<{ poligono: Ponto3[] }>({
      id: 'chao',
      data: [
        {
          poligono: [
            [-80, -80, 0],
            [largura + 80, -80, 0],
            [largura + 80, altura + 80, 0],
            [-80, altura + 80, 0],
          ],
        },
      ],
      getPolygon: (d) => d.poligono,
      getFillColor: CHAO,
    }),
    new PathLayer<{ caminho: Ponto3[] }>({
      id: 'margem',
      data: [{ caminho: cena.rio }],
      getPath: (d) => d.caminho,
      getColor: MARGEM,
      getWidth: 30,
      widthUnits: 'common',
      jointRounded: true,
      capRounded: true,
    }),
    new PathLayer<{ caminho: Ponto3[] }>({
      id: 'rio',
      data: [{ caminho: cena.rio.map(([x, y]) => [x, y, 0.6] as Ponto3) }],
      getPath: (d) => d.caminho,
      getColor: AGUA,
      getWidth: 20,
      widthUnits: 'common',
      jointRounded: true,
      capRounded: true,
    }),
    // Os bairros: placas em relevo. Com um bairro aberto, os outros ficam acinzentados.
    new SolidPolygonLayer<BairroCena>({
      id: 'bairros',
      data: cena.bairros,
      getPolygon: (b) => b.poligono.map(([x, y]) => cena.ponto(x, y, 0)),
      extruded: true,
      getElevation: ALTURA_DA_PLACA,
      getFillColor: (b) => (aberto(b.id) ? b.pastel : misturar(b.pastel, CINZA, 0.45)),
      material: MATERIAL,
      pickable: true,
      updateTriggers: { getFillColor: [bairroAberto] },
      transitions: { getFillColor: 400 },
    }),
    new PathLayer<Cena3D['avenidas'][number]>({
      id: 'avenidas',
      data: cena.avenidas,
      getPath: (a) => a.caminho,
      getColor: PISTA,
      getWidth: 6,
      widthUnits: 'common',
      capRounded: true,
    }),
    new PathLayer<Cena3D['avenidas'][number], PathStyleExtensionProps<Cena3D['avenidas'][number]>>({
      id: 'faixas',
      data: cena.avenidas,
      getPath: (a) => a.caminho.map(([x, y, z]) => [x, y, z + 0.1] as Ponto3),
      getColor: [255, 255, 255, 170],
      getWidth: 1,
      widthUnits: 'pixels',
      getDashArray: [5, 5],
      extensions: [new PathStyleExtension({ dash: true })],
    }),
    // Prédios genéricos: a cidade. No bairro aberto, saem para dar lugar aos sistemas.
    new SolidPolygonLayer<Predio>({
      id: 'predios',
      data: raioX ? [] : cena.predios.filter((p) => p.bairro !== bairroAberto),
      getPolygon: (p) => p.base,
      extruded: true,
      getElevation: (p) => p.altura,
      getFillColor: (p) => (aberto(p.bairro) ? p.cor : misturar(p.cor, CINZA, 0.5)),
      material: MATERIAL,
      updateTriggers: { getFillColor: [bairroAberto] },
    }),
    new ColumnLayer<{ posicao: Ponto3 }>({
      id: 'arvores',
      data: raioX ? [] : cena.arvores.filter((a) => a.bairro !== bairroAberto),
      getPosition: (a) => a.posicao,
      diskResolution: 8,
      radius: 4.5,
      extruded: true,
      getElevation: 8,
      getFillColor: [104, 156, 96, 255],
      material: MATERIAL,
    }),
    new ColumnLayer<{ posicao: Ponto3 }>({
      id: 'copas',
      data: raioX ? [] : cena.arvores.filter((a) => a.bairro !== bairroAberto),
      getPosition: (a) => [a.posicao[0], a.posicao[1], a.posicao[2] + 8],
      diskResolution: 8,
      radius: 2.8,
      extruded: true,
      getElevation: 4,
      getFillColor: [136, 186, 120, 255],
      material: MATERIAL,
    }),
  ];

  // --- Bairro aberto: os sistemas, com o status no telhado -------------------------------
  if (bairroAberto || raioX) {
    const ids = new Set(sistemas.map((n) => n.id));
    lista.push(
      new LineLayer<Cidade['arestas'][number]>({
        id: 'relacoes-internas',
        data: cidade.arestas.filter((a) => ids.has(a.de) && ids.has(a.para)),
        pickable: raioX,
        getSourcePosition: (a) => noNaCena(a.de, ALTURA_DA_PLACA + 0.4)!,
        getTargetPosition: (a) => noNaCena(a.para, ALTURA_DA_PLACA + 0.4)!,
        getColor: [110, 110, 110, 110],
        getWidth: 1.5,
        widthUnits: 'pixels',
      }),
      new SolidPolygonLayer<NoDoMapa>({
        id: 'sistemas',
        data: sistemas,
        getPolygon: (n) => pegada(n, cena),
        extruded: true,
        getElevation: alturaDoNo,
        getFillColor: (n): Cor =>
          n.id === c.selecionado ? misturar(LARANJA, [255, 255, 255, 255], 0.25) : corDoSistema(bairroPorId.get(n.bairro)),
        material: MATERIAL,
        pickable: true,
        updateTriggers: { getFillColor: [c.selecionado] },
      }),
      new SolidPolygonLayer<NoDoMapa>({
        id: 'telhados',
        data: sistemas.filter((n) => n.status),
        getPolygon: (n) => pegada(n, cena, ALTURA_DA_PLACA + alturaDoNo(n) + 0.3, 5),
        getFillColor: (n) => COR_STATUS[n.status ?? 'ok'],
        updateTriggers: { getFillColor: [sistemas.map((n) => n.status).join()] },
      }),
    );
    // Do nó selecionado para os outros bairros: arcos discretos.
    const sel = c.selecionado ? nosVivos.get(c.selecionado) : undefined;
    if (sel) {
      lista.push(
        new ArcLayer<Cidade['arestas'][number]>({
          id: 'relacoes-externas',
          data: cidade.arestas.filter(
            (a) =>
              (a.de === sel.id || a.para === sel.id) &&
              nosVivos.get(a.de === sel.id ? a.para : a.de)?.bairro !== sel.bairro,
          ),
          getSourcePosition: (a) => noNaCena(a.de, ALTURA_DA_PLACA + 2)!,
          getTargetPosition: (a) => noNaCena(a.para, ALTURA_DA_PLACA + 2)!,
          getSourceColor: [242, 101, 34, 200],
          getTargetColor: [29, 53, 87, 200],
          getWidth: 2,
          getHeight: 0.4,
        }),
      );
    }
  }

  // --- As estradas da jornada ------------------------------------------------------------
  const corDaRota = (r: RotaDaJornada): Cor =>
    r.estimativa.bloqueada
      ? COR_STATUS.fora
      : r.id === exibido.rota
        ? LARANJA_CLARO
        : r.id === c.destacada
          ? [60, 60, 60, 240]
          : [100, 100, 100, 200];
  lista.push(
    new PathLayer<RotaDaJornada, PathStyleExtensionProps<RotaDaJornada>>({
      id: 'rotas',
      data: c.rotas,
      getPath: (r) => c.caminhos.get(r.id)?.pontos ?? [],
      getColor: corDaRota,
      getWidth: (r) => (r.id === exibido.rota ? 8 : r.id === c.destacada ? 4 : 3),
      widthUnits: 'pixels',
      jointRounded: true,
      capRounded: true,
      getDashArray: (r: RotaDaJornada): [number, number] => (r.id === exibido.rota ? [0, 0] : [4, 3]),
      dashJustified: true,
      extensions: [new PathStyleExtension({ dash: true })],
      updateTriggers: {
        getColor: [exibido.rota, c.destacada, c.rotas.map((r) => r.estimativa.bloqueada).join()],
        getWidth: [exibido.rota, c.destacada],
        getDashArray: [exibido.rota],
      },
    }),
  );
  const ativa = exibido.rota ? c.caminhos.get(exibido.rota) : undefined;
  if (ativa && c.robo?.arco != null) {
    lista.push(
      // O trecho já percorrido acende em laranja forte, até onde o robô está.
      new TripsLayer<Caminho>({
        id: 'rastro',
        data: [ativa],
        getPath: (d) => d.pontos.map(([x, y, z]) => [x, y, z + 0.1] as Ponto3),
        getTimestamps: (d) => d.comprimentos,
        currentTime: c.robo.arco,
        trailLength: 1e6,
        fadeTrail: false,
        getColor: LARANJA,
        getWidth: 10,
        widthUnits: 'pixels',
        capRounded: true,
        jointRounded: true,
      }),
    );
  }

  // --- Paradas: marcos 3D ------------------------------------------------------------------
  const paradas = paradasDaJornada(c.rotas, exibido.rota).filter((p) => nosVivos.has(p.id));
  if (exibido.pedagio && nosVivos.has('parada-aprovacao-humana') && !paradas.some((p) => p.id === 'parada-aprovacao-humana'))
    paradas.push({ ordem: 0, numero: null, id: 'parada-aprovacao-humana', nome: 'Aprovação', bairro: 'risco' });
  const visitadas = new Set(exibido.visitadas);
  lista.push(
    new SolidPolygonLayer<ParadaDaRota>({
      id: 'paradas',
      data: paradas,
      getPolygon: (p) => {
        const [x, y, z] = noNaCena(p.id)!;
        return octogono(x, y, z, p.id === exibido.parada ? 6 : 4.5);
      },
      extruded: true,
      getElevation: (p) => (p.id === exibido.parada ? 30 : 18),
      getFillColor: (p): Cor =>
        p.id === exibido.parada ? [214, 80, 20, 255] : visitadas.has(p.id) ? LARANJA : [250, 248, 244, 255],
      material: MATERIAL,
      pickable: true,
      updateTriggers: {
        getPolygon: [exibido.parada],
        getElevation: [exibido.parada],
        getFillColor: [exibido.parada, exibido.visitadas.join()],
      },
      transitions: { getElevation: 400 },
    }),
  );
  const atual = exibido.parada ? noNaCena(exibido.parada, ALTURA_DA_PLACA + 0.5) : null;
  if (atual) {
    const fase = (c.agora % 1600) / 1600;
    lista.push(
      new ScatterplotLayer<Ponto3>({
        id: 'anel-da-parada',
        data: [atual],
        getPosition: (p) => p,
        getRadius: 8 + fase * 14,
        radiusUnits: 'common',
        filled: false,
        stroked: true,
        getLineColor: [242, 101, 34, 255 * (1 - fase)],
        lineWidthMinPixels: 2,
        updateTriggers: { getRadius: [c.agora], getLineColor: [c.agora] },
      }),
    );
  }

  // --- Faróis de incidente: visíveis da cidade inteira --------------------------------------
  const comProblema = comProblemaNoTransito(cidade);
  lista.push(
    new SolidPolygonLayer<NoDoMapa>({
      id: 'farois',
      data: comProblema,
      getPolygon: (n) => {
        const [x, y, z] = cena.ponto(n.x, n.y, ALTURA_DA_PLACA);
        return octogono(x, y, z, 2.2);
      },
      extruded: true,
      getElevation: 70,
      getFillColor: (n): Cor => {
        const [r, g, b] = COR_STATUS[n.status ?? 'fora'];
        return [r, g, b, 215];
      },
      updateTriggers: { getFillColor: [comProblema.map((n) => n.status).join()] },
    }),
    new ScatterplotLayer<NoDoMapa>({
      id: 'base-dos-farois',
      data: comProblema,
      getPosition: (n) => cena.ponto(n.x, n.y, ALTURA_DA_PLACA + 0.5),
      getRadius: 12,
      radiusUnits: 'common',
      filled: false,
      stroked: true,
      getLineColor: (n) => COR_STATUS[n.status ?? 'fora'],
      lineWidthMinPixels: 3,
    }),
  );

  // --- Pulsos: o agente chama um sistema (tool.called) ---------------------------------------
  const recentes = exibido.pulsos.filter((p) => c.agora - p.quando < DURACAO_DO_PULSO_MS && nosVivos.has(p.no));
  const idade = (p: Pulso) => (c.agora - p.quando) / DURACAO_DO_PULSO_MS;
  lista.push(
    new ScatterplotLayer<Pulso>({
      id: 'pulsos',
      data: recentes,
      getPosition: (p) => noNaCena(p.no, ALTURA_DA_PLACA + 0.6)!,
      getRadius: (p) => 6 + idade(p) * 26,
      radiusUnits: 'common',
      filled: false,
      stroked: true,
      getLineColor: (p): Cor => (p.ok ? [242, 101, 34, 255 * (1 - idade(p))] : [208, 76, 76, 255 * (1 - idade(p))]),
      lineWidthMinPixels: 3,
      updateTriggers: { getRadius: [c.agora], getLineColor: [c.agora] },
    }),
  );
  if (c.robo) {
    const origem: Ponto3 = [c.robo.posicao[0], c.robo.posicao[1], Z_ESTRADA + ALTURA_DO_ROBO];
    lista.push(
      new ArcLayer<Pulso>({
        id: 'chamadas',
        data: recentes,
        getSourcePosition: () => origem,
        getTargetPosition: (p) => noNaCena(p.no, ALTURA_DA_PLACA + 1)!,
        getSourceColor: (p): Cor => [242, 101, 34, 230 * (1 - idade(p))],
        getTargetColor: (p): Cor => (p.ok ? [242, 101, 34, 230 * (1 - idade(p))] : [208, 76, 76, 230 * (1 - idade(p))]),
        getWidth: 3,
        getHeight: 0.35,
        updateTriggers: { getSourcePosition: [origem.join()], getSourceColor: [c.agora], getTargetColor: [c.agora] },
      }),
    );
  }

  // --- O robô e a chegada ------------------------------------------------------------------------
  if (exibido.fim?.apolice) {
    const ultima = exibido.parada ? noNaCena(exibido.parada) : null;
    if (ultima)
      lista.push(
        new IconLayer<Ponto3>({
          id: 'chegada',
          data: [[ultima[0] + 14, ultima[1] + 4, ultima[2]]],
          getPosition: (p) => p,
          getIcon: () => ICONE_CHEGADA,
          getSize: 64,
          sizeUnits: 'pixels',
        }),
      );
  }
  if (c.robo) {
    lista.push(
      new ScatterplotLayer<Ponto3>({
        id: 'sombra-do-robo',
        data: [c.robo.posicao],
        getPosition: ([x, y]) => [x, y, Z_ESTRADA + 0.2],
        getRadius: 6,
        radiusUnits: 'common',
        getFillColor: [0, 0, 0, 80],
      }),
      // O robô voa um pouco acima dos marcos e é sempre desenhado por cima: nunca some atrás de um prédio.
      new LineLayer<Ponto3>({
        id: 'fio-do-robo',
        data: [c.robo.posicao],
        getSourcePosition: ([x, y]) => [x, y, Z_ESTRADA + 0.2],
        getTargetPosition: ([x, y]) => [x, y, Z_ESTRADA + ALTURA_DO_ROBO],
        getColor: [29, 53, 87, 140],
        getWidth: 2,
        widthUnits: 'pixels',
      }),
      new IconLayer<Ponto3>({
        id: 'robo',
        data: [c.robo.posicao],
        getPosition: ([x, y]) => [x, y, Z_ESTRADA + ALTURA_DO_ROBO],
        getIcon: () => ICONE_ROBO,
        getSize: 80,
        sizeUnits: 'pixels',
        parameters: { depthCompare: 'always' },
      }),
    );
  }

  return lista;
}
