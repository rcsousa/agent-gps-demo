// Modo Mapa: a cidade do banco em 3D (o grafo) e a viagem do agente (os eventos), lado a lado.

import { Add, ArrowLeft, Play, Subtract, ZoomFit } from '@carbon/icons-react';
import { Button, Dropdown, IconButton, InlineNotification, Tag, Toggle } from '@carbon/react';
import { AmbientLight, DirectionalLight, LightingEffect, LinearInterpolator, OrbitView } from '@deck.gl/core';
import DeckGL, { type DeckGLRef } from '@deck.gl/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { aplicarIncidente, api, viagem as apiViagem } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import { navegar, parametro, useMudancaDeEndereco } from '../navegacao';
import { PainelLateral } from '../status/Painel';
import type { Cidade, EstadoDoModelo, NoDoMapa, RotaDaJornada } from '../tipos';
import {
  ALTURA_DO_ROBO,
  camadas,
  comProblemaNoTransito,
  DURACAO_DO_PULSO_MS,
  paradasDaJornada,
  type Robo,
  sistemasDoBairro,
} from './camadas';
import {
  ALTURA_DA_PLACA,
  alturaDoSistema,
  type Caminho,
  caminhoDaRota,
  montarCena,
  type Ponto3,
  pontoNoCaminho,
  suave,
} from './cidade3d';
import { DESLOCAMENTO_MS, useDiretor } from './diretor';
import { LinhaDoTempo } from './LinhaDoTempo';
import { CartaoDeRotas, Conversa, DetalheDoNo, Legenda } from './Paineis';
import { type Rotulo, Rotulos } from './rotulos';
import { useViagem } from './viagem';

const t = mensagens.mapa;
const INTERVALO_TRANSITO_MS = 5000;
// Uma só instância: recriar a vista a cada quadro reinicia o controle.
const VISTA = new OrbitView({ id: 'cidade', orbitAxis: 'Z', fovy: 40 });
const CONTROLE = { dragMode: 'pan' as const, scrollZoom: { speed: 0.01, smooth: true } };
const LUZ = new LightingEffect({
  ambiente: new AmbientLight({ color: [255, 255, 255], intensity: 1.0 }),
  sol: new DirectionalLight({ color: [255, 250, 240], intensity: 1.6, direction: [-2, -4, -6] }),
});
const INCLINACAO = 52;
const GIRO = -14;
// A partir desse zoom (relativo à cidade inteira), o bairro sob o centro da câmera se abre.
const NIVEL_DO_BAIRRO = 0.85;
// Os rótulos não invadem a linha do tempo do rodapé (5,75rem).
const ALTURA_DA_LINHA_DO_TEMPO_PX = 92;
const ZOOM_NO_BAIRRO = 1.35; // seguindo o agente
const ZOOM_DO_BAIRRO = 1.75; // ao clicar no bairro: perto o bastante para as placas dos sistemas

interface Opcao {
  id: string;
  texto: string;
}

const MODOS: Opcao[] = [
  { id: 'com_skill', texto: t.barra.modos.com_skill },
  { id: 'sem_skill', texto: t.barra.modos.sem_skill },
  { id: 'sem_contexto', texto: t.barra.modos.sem_contexto },
];
const CANAIS: Opcao[] = [
  { id: 'app', texto: t.barra.canais.app },
  { id: 'agencia', texto: t.barra.canais.agencia },
  { id: 'central', texto: t.barra.canais.central },
];
const ROTEIRO = 'roteiro';
const PONTO_DE_PARTIDA: Record<string, string> = {
  app: 'canal-app',
  agencia: 'canal-agencia',
  central: 'canal-central',
};

// Presets das cenas (vindas da tela de abertura). O que acontece depois é sempre real.
const CENAS: Record<string, { modo?: string; incidente?: string }> = {
  '1': {},
  '2': { modo: 'sem_contexto' },
  '3': { modo: 'sem_skill' },
  '4': { modo: 'com_skill' },
  '5': { modo: 'com_skill' },
  '6': { modo: 'com_skill', incidente: 'cotacao-ancora-fora' },
  '7': { modo: 'com_skill', incidente: 'alcada-ana-excedida' },
};

interface Visao {
  target: [number, number, number];
  zoom: number;
  rotationX: number;
  rotationOrbit: number;
  minRotationX?: number;
  maxRotationX?: number;
  transitionDuration?: number;
  transitionInterpolator?: LinearInterpolator;
}

function enquadramento(largura: number, altura: number, cidade: Cidade): Visao {
  const mundo = cidade.mundo;
  const escala = Math.min(largura / mundo.largura, (altura * 1.25) / mundo.altura) * 0.88;
  return {
    target: [mundo.largura / 2 - 40, mundo.altura / 2 - 10, 0],
    zoom: Math.log2(Math.max(escala, 0.05)),
    rotationX: INCLINACAO,
    rotationOrbit: GIRO,
    minRotationX: 25,
    maxRotationX: 88,
  };
}

// O pino do robô (80 px, preso pela ponta) não pode ficar atrás de um rótulo.
function espacoDoRobo(robo: Robo | null, projetar: (p: Ponto3) => [number, number]) {
  if (!robo) return [];
  const [x, y] = projetar([robo.posicao[0], robo.posicao[1], ALTURA_DA_PLACA + 0.6 + ALTURA_DO_ROBO]);
  return [[x - 34, y - 84, x + 34, y + 4] as [number, number, number, number]];
}

const chaveDaGeometria = (cidade: Cidade | null, rotas: RotaDaJornada[]) =>
  cidade
    ? `${cidade.bairros.map((b) => b.id).join()}|${cidade.nos.length}|${rotas.map((r) => r.paradas.map((p) => p.id).join()).join('/')}`
    : '';

export function PaginaMapa() {
  const [execucao, setExecucao] = useState<string | null>(() => parametro('execucao'));
  const [cena, setCena] = useState<string | null>(() => parametro('cena'));
  useMudancaDeEndereco(
    useCallback(() => {
      setExecucao(parametro('execucao'));
      setCena(parametro('cena'));
    }, []),
  );
  // A conversa usa o estado real; o mapa, o que o diretor já exibiu.
  const real = useViagem(execucao);
  const direcao = useDiretor(real);
  const exibido = direcao.exibido;

  const [cidade, setCidade] = useState<Cidade | null>(null);
  const [rotas, setRotas] = useState<RotaDaJornada[]>([]);
  const [modelo, setModelo] = useState<EstadoDoModelo | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  // Trânsito: a cidade e as rotas são relidas a cada 5 s (o simulador muda o mundo).
  const consultar = useCallback(async () => {
    try {
      const [c, r] = await Promise.all([api.cidade(), api.rotas()]);
      setCidade(c);
      setRotas(r.rotas);
      setErro(null);
    } catch {
      setErro(t.erroCidade);
    }
  }, []);
  useEffect(() => {
    consultar();
    api.modelo().then(setModelo, () => setModelo(null));
    const id = setInterval(consultar, INTERVALO_TRANSITO_MS);
    return () => clearInterval(id);
  }, [consultar]);

  // A geometria (prédios, estradas) só é refeita se o grafo mudar de forma, não a cada leitura.
  const chave = chaveDaGeometria(cidade, rotas);
  const cena3d = useMemo(() => (cidade ? montarCena(cidade, rotas) : null), [chave]); // eslint-disable-line react-hooks/exhaustive-deps
  const caminhos = useMemo(
    () => new Map<string, Caminho>(cena3d ? rotas.map((r) => [r.id, caminhoDaRota(r, cena3d)]) : []),
    [cena3d], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const nos = useMemo(() => new Map((cidade?.nos ?? []).map((n) => [n.id, n])), [cidade]);

  // --- Câmera -------------------------------------------------------------------------
  const area = useRef<HTMLDivElement>(null);
  const deck = useRef<DeckGLRef>(null);
  const inicioDoClique = useRef<[number, number] | null>(null);
  const [tamanho, setTamanho] = useState<[number, number]>([0, 0]);
  const [base, setBase] = useState<Visao | null>(null);
  const [visao, setVisao] = useState<Visao | null>(null);
  const [seguir, setSeguir] = useState(true);

  useEffect(() => {
    if (!area.current) return;
    const observador = new ResizeObserver(([e]) => setTamanho([e.contentRect.width, e.contentRect.height]));
    observador.observe(area.current);
    return () => observador.disconnect();
  }, []);

  useEffect(() => {
    if (!cidade || base || !tamanho[0]) return;
    const inicial = enquadramento(tamanho[0], tamanho[1], cidade);
    setBase(inicial);
    setVisao(inicial);
  }, [cidade, base, tamanho]);

  const voar = useCallback(
    (alvo: Ponto3, zoomRelativo: number, duracao = 900) => {
      if (!base) return;
      setVisao((atual) => ({
        ...(atual ?? base),
        target: [alvo[0], alvo[1], 0],
        zoom: base.zoom + zoomRelativo,
        transitionDuration: duracao,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
      }));
    },
    [base],
  );
  const pontoDoNo = useCallback(
    (id: string, z = ALTURA_DA_PLACA): Ponto3 | null => {
      const n = nos.get(id);
      return n && cena3d ? cena3d.ponto(n.x, n.y, z) : null;
    },
    [nos, cena3d],
  );
  const voarParaBairro = useCallback(
    (id: string) => {
      const b = cena3d?.bairros.find((x) => x.id === id);
      if (b) voar(b.centro, ZOOM_DO_BAIRRO);
    },
    [cena3d, voar],
  );
  const voltarACidade = useCallback(() => {
    if (base)
      setVisao({
        ...base,
        transitionDuration: 900,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom', 'rotationX', 'rotationOrbit']),
      });
  }, [base]);

  // O bairro aberto deriva da câmera: perto o bastante, abre o bairro sob o centro.
  const nivel = visao && base ? visao.zoom - base.zoom : 0;
  const bairroAberto =
    visao && cena3d && nivel >= NIVEL_DO_BAIRRO ? cena3d.bairroDe(visao.target[0], visao.target[1]) : null;

  // ?parada=N (da tela de abertura): o mapa abre naquela parada, com o bairro aberto.
  useEffect(() => {
    const numero = parametro('parada');
    const alvo = paradasDaJornada(rotas, null).find((p) => String(p.numero) === numero);
    const ponto = alvo && pontoDoNo(alvo.id);
    if (ponto && base) voar(ponto, ZOOM_NO_BAIRRO);
  }, [rotas, base, pontoDoNo, voar]);

  // "Seguir o agente": a câmera vai junto com o robô, no mesmo ritmo, e abre o bairro de chegada.
  useEffect(() => {
    const destino = direcao.trecho && pontoDoNo(direcao.trecho.para);
    if (seguir && destino) voar(destino, ZOOM_NO_BAIRRO, DESLOCAMENTO_MS);
  }, [seguir, direcao.trecho, pontoDoNo, voar]);

  // --- Relógio: só corre enquanto há o que animar ----------------------------------------
  const [agora, setAgora] = useState(() => performance.now());
  const ultimoPulso = exibido.pulsos.at(-1)?.quando ?? 0;
  const animando =
    Boolean(exibido.id && (!exibido.fim || direcao.fila > 0)) || agora - ultimoPulso < DURACAO_DO_PULSO_MS;
  useEffect(() => {
    if (!animando) return;
    let quadro = 0;
    const passo = (instante: number) => {
      setAgora(instante);
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [animando]);

  // --- O robô: anda pela estrada quando o diretor exibe um step.started ---------------------
  const robo: Robo | null = useMemo(() => {
    if (!exibido.modo || !cena3d) return null;
    const partidaNo = nos.get(PONTO_DE_PARTIDA[exibido.canal ?? 'app'] ?? 'canal-app');
    const z = ALTURA_DA_PLACA + 0.6;
    const partida: Ponto3 = partidaNo ? cena3d.ponto(partidaNo.x, partidaNo.y, z) : [0, 0, z];
    const ativa = exibido.rota ? caminhos.get(exibido.rota) : undefined;
    const arco = (id: string | null) => (id && ativa ? (ativa.arcoDaParada.get(id) ?? null) : null);
    const lugar = (id: string | null): Ponto3 => {
      const s = arco(id);
      if (ativa && s != null) return pontoNoCaminho(ativa, s);
      return (id && pontoDoNo(id, z)) || partida;
    };
    if (!exibido.parada) return { posicao: partida, arco: ativa ? 0 : null };
    const tr = direcao.trecho;
    const progresso = tr ? Math.min((agora - tr.inicio) / DESLOCAMENTO_MS, 1) : 1;
    if (tr && tr.para === exibido.parada && progresso < 1) {
      const k = suave(progresso);
      const a0 = arco(tr.de);
      const a1 = arco(tr.para);
      if (ativa && a0 != null && a1 != null && a1 > a0) {
        const s = a0 + (a1 - a0) * k;
        return { posicao: pontoNoCaminho(ativa, s), arco: s };
      }
      const p0 = lugar(tr.de);
      const p1 = lugar(tr.para);
      return {
        posicao: [p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k, z],
        arco: a0,
      };
    }
    return { posicao: lugar(exibido.parada), arco: arco(exibido.parada) };
  }, [
    exibido.modo,
    exibido.canal,
    exibido.rota,
    exibido.parada,
    direcao.trecho,
    agora,
    cena3d,
    caminhos,
    nos,
    pontoDoNo,
  ]);

  const [destacada, setDestacada] = useState<string | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);

  const listaDeCamadas = useMemo(
    () =>
      cena3d && cidade
        ? camadas({
            cena: cena3d,
            cidade,
            rotas,
            caminhos,
            exibido,
            agora,
            bairroAberto,
            destacada,
            selecionado,
            robo,
          })
        : [],
    [cena3d, cidade, rotas, caminhos, exibido, agora, bairroAberto, destacada, selecionado, robo],
  );

  // --- Rótulos em HTML ----------------------------------------------------------------------
  const projetar = useMemo(() => {
    if (!visao || !tamanho[0]) return null;
    const viewport = VISTA.makeViewport({ width: tamanho[0], height: tamanho[1], viewState: visao });
    if (!viewport) return null;
    return (p: Ponto3) => viewport.project(p) as [number, number];
  }, [visao, tamanho]);

  const paradas = useMemo(() => paradasDaJornada(rotas, exibido.rota), [rotas, exibido.rota]);
  const rotulos: Rotulo[] = useMemo(() => {
    if (!cena3d || !cidade) return [];
    const lista: Rotulo[] = [];
    const visitadas = new Set(exibido.visitadas);
    for (const b of cena3d.bairros) {
      if (b.id === bairroAberto) continue;
      lista.push({
        id: `bairro-${b.id}`,
        tipo: 'bairro',
        texto: b.nome,
        posicao: [b.centro[0], b.centro[1], 46],
        prioridade: 1,
        estado: bairroAberto ? 'esmaecido' : undefined,
        aoClicar: () => voarParaBairro(b.id),
      });
    }
    for (const p of paradas) {
      const atual = p.id === exibido.parada;
      const ponto = pontoDoNo(p.id, ALTURA_DA_PLACA + (atual ? 0 : 20));
      if (!ponto || p.numero == null) continue;
      lista.push({
        id: `parada-${p.id}`,
        tipo: 'parada',
        texto: p.nome,
        numero: p.numero,
        posicao: ponto,
        prioridade: atual ? 0.5 : 2,
        estado: atual ? 'atual' : visitadas.has(p.id) ? 'feita' : 'pendente',
        abaixo: atual && Boolean(exibido.modo),
        aoClicar: () => setSelecionado(p.id),
      });
    }
    const incidentes = comProblemaNoTransito(cidade);
    for (const n of incidentes) {
      lista.push({
        id: `incidente-${n.id}`,
        tipo: 'incidente',
        texto: n.nome,
        status: n.status,
        posicao: cena3d.ponto(n.x, n.y, ALTURA_DA_PLACA + 72),
        prioridade: 0,
        aoClicar: () => setSelecionado(n.id),
      });
    }
    if (exibido.pedagio) {
      const ponto = pontoDoNo('parada-aprovacao-humana', ALTURA_DA_PLACA + 22);
      if (ponto) lista.push({ id: 'pedagio', tipo: 'pedagio', texto: t.pedagio, posicao: ponto, prioridade: 0.4 });
    }
    for (const n of sistemasDoBairro(cidade, bairroAberto)) {
      if (incidentes.includes(n)) continue; // já tem o rótulo do farol
      lista.push({
        id: `sistema-${n.id}`,
        tipo: 'sistema',
        texto: n.nome,
        status: n.status,
        posicao: cena3d.ponto(n.x, n.y, ALTURA_DA_PLACA + alturaDoSistema(n) + 1),
        prioridade: n.id === selecionado ? 1 : 4,
        aoClicar: () => setSelecionado(n.id),
      });
    }
    return lista;
  }, [
    cena3d,
    cidade,
    paradas,
    exibido.parada,
    exibido.visitadas,
    exibido.pedagio,
    bairroAberto,
    selecionado,
    pontoDoNo,
    voarParaBairro,
  ]);

  // --- Barra de viagem ----------------------------------------------------------------
  const preset = (cena && CENAS[cena]) || {};
  const [modo, setModo] = useState<string>(preset.modo ?? 'com_skill');
  const [canal, setCanal] = useState('app');
  const [escolhaDeModelo, setEscolhaDeModelo] = useState<string | null>(null);
  const [incidenteAplicado, setIncidenteAplicado] = useState(false);
  useEffect(() => {
    if (preset.modo) setModo(preset.modo);
    setIncidenteAplicado(false);
  }, [cena]); // eslint-disable-line react-hooks/exhaustive-deps

  const opcoesDeModelo: Opcao[] = [
    ...(modelo?.modelos ?? []).map((m) => ({ id: m.id, texto: t.barra.modelo(m.id) })),
    { id: ROTEIRO, texto: t.barra.roteiro },
  ];
  const modeloEscolhido = escolhaDeModelo ?? modelo?.modelo ?? ROTEIRO;

  async function iniciar() {
    try {
      const pedido =
        modeloEscolhido === ROTEIRO ? { modo, canal, provedor: ROTEIRO } : { modo, canal, modelo: modeloEscolhido };
      const { id } = await apiViagem.iniciar(pedido);
      voltarACidade();
      navegar(`/mapa?execucao=${id}${cena ? `&cena=${cena}` : ''}`);
    } catch {
      setErro(t.erroIniciar);
    }
  }

  async function derrubar() {
    if (!preset.incidente) return;
    try {
      await aplicarIncidente(preset.incidente);
      setIncidenteAplicado(true);
      consultar();
    } catch {
      setErro(t.erroIncidente);
    }
  }

  const emAndamento = Boolean(real.id && !real.fim);
  const ultimoIncidente = exibido.incidentes.at(-1);
  const ultimoRecalculo = exibido.recalculos.at(-1);
  const noSelecionado = selecionado ? nos.get(selecionado) : undefined;
  const nomeDoBairroAberto = cena3d?.bairros.find((b) => b.id === bairroAberto)?.nome;

  return (
    <section
      className="mapa"
      aria-labelledby="titulo-mapa"
      // Estado observável para os testes e2e (o mapa em si é um canvas).
      data-execucao={real.id ?? ''}
      data-parada={exibido.parada ?? ''}
      data-visitadas={exibido.visitadas.length}
      data-bairro-aberto={bairroAberto ?? ''}
      data-fila={direcao.fila}
    >
      <div className="mapa__barra">
        <h1 id="titulo-mapa" className="mapa__titulo">
          {t.titulo}
        </h1>
        <Dropdown
          id="viagem-modo"
          size="md"
          titleText={t.barra.modo}
          label={t.barra.modo}
          items={MODOS}
          itemToString={(o: Opcao | null) => o?.texto ?? ''}
          selectedItem={MODOS.find((o) => o.id === modo)}
          onChange={({ selectedItem }: { selectedItem: Opcao | null }) => selectedItem && setModo(selectedItem.id)}
          disabled={emAndamento}
        />
        <Dropdown
          id="viagem-canal"
          size="md"
          titleText={t.barra.canal}
          label={t.barra.canal}
          items={CANAIS}
          itemToString={(o: Opcao | null) => o?.texto ?? ''}
          selectedItem={CANAIS.find((o) => o.id === canal)}
          onChange={({ selectedItem }: { selectedItem: Opcao | null }) => selectedItem && setCanal(selectedItem.id)}
          disabled={emAndamento}
        />
        <Dropdown
          id="viagem-modelo"
          size="md"
          titleText={t.barra.modeloRotulo}
          label={t.barra.modeloRotulo}
          items={opcoesDeModelo}
          itemToString={(o: Opcao | null) => o?.texto ?? ''}
          selectedItem={opcoesDeModelo.find((o) => o.id === modeloEscolhido) ?? null}
          onChange={({ selectedItem }: { selectedItem: Opcao | null }) =>
            selectedItem && setEscolhaDeModelo(selectedItem.id)
          }
          disabled={emAndamento}
        />
        <Button id="iniciar-viagem" size="md" renderIcon={Play} onClick={iniciar} disabled={emAndamento}>
          {emAndamento ? t.barra.emViagem : t.barra.iniciar}
        </Button>
        {cena && (
          <div className="mapa__cena">
            <Tag type="warm-gray" size="md">
              {t.cena(cena)}
            </Tag>
            {preset.incidente && (
              <Button kind="danger--tertiary" size="md" onClick={derrubar} disabled={incidenteAplicado}>
                {incidenteAplicado ? t.incidenteAplicado : t.incidentes[preset.incidente]}
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="mapa__corpo">
        <div ref={area} className="mapa__area">
          {erro && (
            <InlineNotification
              kind="error"
              lowContrast
              title={erro}
              onClose={() => setErro(null)}
              className="mapa__erro"
            />
          )}
          {cena3d && visao && (
            // O clique é tratado aqui, com pickObject síncrono (o onClick do deck.gl, assíncrono,
            // se perde enquanto o relógio da animação re-renderiza a página).
            <div
              className="mapa__tela"
              onPointerDown={(e) => (inicioDoClique.current = [e.clientX, e.clientY])}
              onClick={(e) => {
                if ((e.target as HTMLElement).closest('.rotulo')) return; // o rótulo trata o próprio clique
                const [x0, y0] = inicioDoClique.current ?? [e.clientX, e.clientY];
                if (Math.hypot(e.clientX - x0, e.clientY - y0) > 5) return; // foi arrasto
                const caixa = e.currentTarget.getBoundingClientRect();
                const info = deck.current?.pickObject({
                  x: e.clientX - caixa.left,
                  y: e.clientY - caixa.top,
                  radius: 4,
                  layerIds: ['sistemas', 'paradas', 'bairros'],
                });
                if (!info?.object) return;
                if (info.layer?.id === 'bairros') voarParaBairro((info.object as { id: string }).id);
                else setSelecionado((info.object as { id: string }).id);
              }}
            >
              <DeckGL
                ref={deck}
                views={VISTA}
                viewState={visao}
                onViewStateChange={({ viewState }) => setVisao(viewState as Visao)}
                controller={CONTROLE}
                effects={[LUZ]}
                layers={listaDeCamadas}
                getCursor={({ isHovering, isDragging }) =>
                  isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab'
                }
                getTooltip={({ object, layer }) =>
                  object && layer?.id === 'sistemas'
                    ? { text: `${(object as NoDoMapa).nome}\n${(object as NoDoMapa).tipo_exibicao}` }
                    : null
                }
              />
              {projetar && (
                <Rotulos
                  rotulos={rotulos}
                  projetar={projetar}
                  largura={tamanho[0]}
                  altura={tamanho[1] - ALTURA_DA_LINHA_DO_TEMPO_PX}
                  reservado={espacoDoRobo(robo, projetar)}
                />
              )}
            </div>
          )}

          <CartaoDeRotas rotas={rotas} ativa={exibido.rota} aoDestacar={setDestacada} />

          <div className="mapa__estado">
            {real.id && (
              <Tag type={direcao.fila > 0 ? 'warm-gray' : 'green'} size="md">
                {direcao.fila > 0 ? t.reproduzindo(direcao.fila) : real.fim ? t.encerrada : t.aoVivo}
              </Tag>
            )}
            {direcao.fila > 3 && (
              <Button kind="ghost" size="sm" onClick={direcao.pularParaOFim}>
                {t.pularParaOFim}
              </Button>
            )}
            {bairroAberto && (
              <Button kind="secondary" size="sm" renderIcon={ArrowLeft} onClick={voltarACidade}>
                {t.voltarACidade(nomeDoBairroAberto ?? '')}
              </Button>
            )}
          </div>

          <div className="mapa__avisos" aria-live="assertive">
            {ultimoIncidente && (
              <InlineNotification
                kind="error"
                lowContrast
                hideCloseButton
                title={ultimoIncidente.metafora}
                subtitle={ultimoIncidente.descricao}
              />
            )}
            {ultimoRecalculo && (
              <InlineNotification
                kind="warning"
                lowContrast
                hideCloseButton
                title={t.recalculo(ultimoRecalculo.de, ultimoRecalculo.para)}
                subtitle={`${ultimoRecalculo.motivo} ${t.regra}: ${ultimoRecalculo.regra}`}
              />
            )}
            {exibido.motivoDaRota && !ultimoRecalculo && !exibido.fim && (
              <InlineNotification
                kind="info"
                lowContrast
                hideCloseButton
                title={t.rotaEscolhida}
                subtitle={exibido.motivoDaRota}
              />
            )}
            {exibido.fim && (
              <InlineNotification
                kind={exibido.fim.apolice ? 'success' : exibido.fim.status === 'concluida' ? 'info' : 'error'}
                lowContrast
                hideCloseButton
                title={exibido.fim.apolice ? t.fim.apolice(exibido.fim.apolice) : t.fim.status(exibido.fim.status)}
                subtitle={t.fim.detalhe(exibido.fim.duracao, exibido.fim.custo, exibido.modelo)}
              />
            )}
          </div>

          <Legenda />

          <div className="mapa__controles">
            <Toggle
              id="seguir-agente"
              size="sm"
              labelText={t.seguir}
              hideLabel
              labelA={t.seguir}
              labelB={t.seguir}
              toggled={seguir}
              onToggle={setSeguir}
            />
            <IconButton
              kind="secondary"
              label={t.aproximar}
              onClick={() => setVisao((v) => v && { ...v, zoom: v.zoom + 0.5, transitionDuration: 300 })}
            >
              <Add />
            </IconButton>
            <IconButton
              kind="secondary"
              label={t.afastar}
              onClick={() => setVisao((v) => v && { ...v, zoom: v.zoom - 0.5, transitionDuration: 300 })}
            >
              <Subtract />
            </IconButton>
            <IconButton kind="secondary" label={t.enquadrar} onClick={voltarACidade}>
              <ZoomFit />
            </IconButton>
          </div>

          <LinhaDoTempo paradas={paradas} viagem={exibido} />
        </div>

        <Conversa
          viagem={real}
          aoResponder={(texto) => apiViagem.responder(real.id!, texto).then(() => undefined)}
        />
      </div>

      {noSelecionado && (
        <PainelLateral
          tipo={noSelecionado.tipo_exibicao}
          titulo={noSelecionado.nome}
          aoFechar={() => setSelecionado(null)}
        >
          <DetalheDoNo
            key={noSelecionado.id}
            id={noSelecionado.id}
            aoEscolher={(id) => {
              setSelecionado(id);
              const vizinho = pontoDoNo(id);
              if (vizinho) voar(vizinho, ZOOM_NO_BAIRRO + 0.2);
            }}
          />
        </PainelLateral>
      )}
    </section>
  );
}
