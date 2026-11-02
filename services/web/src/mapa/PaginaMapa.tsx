// Modo Mapa: a cidade do banco (o grafo, em ruas e quadras) e a viagem do agente (os eventos).

import {
  Add,
  Book,
  ChevronDown,
  ChevronUp,
  Compass,
  Play,
  PresentationFile,
  RotateClockwise,
  RotateCounterclockwise,
  Subtract,
  ZoomFit,
} from '@carbon/icons-react';
import { Button, ContentSwitcher, Dropdown, IconButton, InlineNotification, Switch, Tag, Toggle } from '@carbon/react';
import { AmbientLight, DirectionalLight, LightingEffect, LinearInterpolator, OrbitView } from '@deck.gl/core';
import DeckGL, { type DeckGLRef } from '@deck.gl/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { aplicarIncidente, api, gravar, incidentesAtivos, simulador, viagem as apiViagem } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import { navegar, parametro, useMudancaDeEndereco } from '../navegacao';
import { Apresentador } from '../apresentador/Apresentador';
import { CAPITULO_DAS_CENAS, cena as presetDaCena } from '../apresentador/cenas';
import { abrirBastidores } from '../bastidores/PainelDeBastidores';
import { PainelRaioX } from '../raiox/PainelRaioX';
import { PainelLateral } from '../status/Painel';
import type { Cidade, EstadoDoModelo, Gravacao, NoDoMapa, Ponto, RotaDaJornada } from '../tipos';
import {
  ALTURA_DO_ROBO,
  camadas,
  comProblemaNoTransito,
  DURACAO_DO_PULSO_MS,
  paradasDaJornada,
  type Rastro,
} from './camadas';
import { ESTILOS } from './construcoes';
import { montarCena, type Ponto3, pontoDaPorta, suave, Z_CHAO, Z_RUA } from './cidade3d';
import { Balao } from './Balao';
import { useDiretor } from './diretor';
import { movimentoReduzido, useTelao } from '../telao';
import { LinhaDoTempo } from './LinhaDoTempo';
import { Conversa, DetalheDoNo, Legenda } from './Paineis';
import { type Rotulo, Rotulos } from './rotulos';
import { caminhoPelasRuas, duracaoDoTrecho, pontoNoTrajeto, type Trajeto, trajeto } from './ruas';
import { ehReplay, PREFIXO_GRAVACAO, useViagem } from './viagem';

const t = mensagens.mapa;
const INTERVALO_TRANSITO_MS = 5000;
// Uma só instância: recriar a vista a cada quadro reinicia o controle.
const VISTA = new OrbitView({ id: 'cidade', orbitAxis: 'Z', fovy: 40 });
const CONTROLE = { dragMode: 'pan' as const, scrollZoom: { speed: 0.01, smooth: true } };
const LUZ = new LightingEffect({
  ambiente: new AmbientLight({ color: [255, 255, 255], intensity: 0.85 }),
  // O sol vem do sudeste, baixo: ilumina as fachadas voltadas para a câmera e marca as janelas.
  sol: new DirectionalLight({ color: [255, 248, 235], intensity: 1.7, direction: [-3, 4, -4] }),
});
// Vista aérea (a cidade inteira, e ao fim da viagem) e vista de GPS (baixa, atrás do robô).
const INCLINACAO = 55;
const INCLINACAO_GPS = 34;
const ZOOM_GPS = 1.45;
// A câmera alcança o robô com essa constante de tempo: segue sem trancos, em qualquer taxa de quadros.
const TEMPO_DA_CAMERA_MS = 220;
// No GPS, a câmera mira esse tanto à frente do robô, na direção da viagem (visão traseira).
const AVANCO_DA_CAMERA = 45;
// O giro é mais lento que o resto da câmera: a cada esquina, o mapa vira sem dar tontura.
const TEMPO_DO_GIRO_MS = 650;
// rotationOrbit = SENTIDO_DO_GIRO × rumo deixa a direção da viagem para cima na tela.
const SENTIDO_DO_GIRO = -1;
const PASSO_DO_GIRO = 15;
const PASSO_DA_INCLINACAO = 10;
// Ângulo em (-180, 180]: o giro sempre pelo menor caminho.
const normalizar = (graus: number) => ((((graus + 180) % 360) + 360) % 360) - 180;
// Sem giro: o norte fica para cima e a profundidade vem só da inclinação da câmera.
const GIRO = 0;
// A partir desse zoom (relativo à cidade inteira), aparecem os nomes das construções.
const NIVEL_DOS_NOMES = 0.75;
// Os rótulos não invadem a linha do tempo do rodapé (5,75rem).
const ALTURA_DA_LINHA_DO_TEMPO_PX = 92;
const ZOOM_SEGUINDO = 1.25; // seguindo o agente pelas ruas
const ZOOM_DO_BAIRRO = 1.1; // ao clicar no nome de um bairro

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
const CHAVE_PASSO_A_PASSO = 'bussola:passo-a-passo';

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
  const escala = Math.min(largura / mundo.largura, (altura * 1.25) / mundo.altura) * 0.92;
  return {
    // Um pouco ao sul do centro: a linha do tempo do rodapé não cobre os bairros de baixo.
    target: [mundo.largura / 2, mundo.altura / 2 - 40, 0],
    zoom: Math.log2(Math.max(escala, 0.05)),
    rotationX: INCLINACAO,
    rotationOrbit: GIRO,
    minRotationX: 25,
    maxRotationX: 88,
  };
}

// O pino do robô (72 px, preso pela ponta) não pode ficar atrás de um rótulo.
function espacoDoRobo(robo: Ponto3 | null, projetar: (p: Ponto3) => [number, number], escala: number) {
  if (!robo) return [];
  const [x, y] = projetar([robo[0], robo[1], Z_RUA + 0.3 + ALTURA_DO_ROBO]);
  return [[x - 32 * escala, y - 78 * escala, x + 32 * escala, y + 4] as [number, number, number, number]];
}

// Cena → gravação para o replay. As cenas 4 (o destino) e 8 (o Raio-X) são a mesma viagem da 5.
const MESMA_VIAGEM_DA: Record<string, string> = { '4': '5', '8': '5' };
function gravacoesPorCena(gravacoes: Gravacao[]): Record<string, string> {
  const porCena: Record<string, string> = Object.fromEntries(
    gravacoes.filter((g) => g.cena).map((g) => [g.cena as string, g.nome]),
  );
  for (const [cena, origem] of Object.entries(MESMA_VIAGEM_DA))
    if (!porCena[cena] && porCena[origem]) porCena[cena] = porCena[origem];
  return porCena;
}

// As construções (corpo e detalhe de cada estilo) respondem ao clique.
const CAMADAS_CLICAVEIS = ESTILOS.flatMap((e) => [`construcao-${e}`, `detalhe-${e}`, `vidro-${e}`]);

const chaveDaGeometria = (cidade: Cidade | null) =>
  cidade ? `${cidade.cidade.xs.join()}|${cidade.cidade.ys.join()}|${cidade.nos.map((n) => n.id).join()}` : '';

export function PaginaMapa() {
  const [execucao, setExecucao] = useState<string | null>(() => parametro('execucao'));
  const [cena, setCena] = useState<string | null>(() => parametro('cena'));
  // Mapa (executivo) ou Raio-X (técnico): a mesma viagem, só muda a apresentação.
  const [raioX, setRaioX] = useState(() => parametro('visao') === 'raio-x');
  const [gravacao, setGravacao] = useState<string | null>(() => parametro('gravacao'));
  useMudancaDeEndereco(
    useCallback(() => {
      setGravacao(parametro('gravacao'));
      setExecucao(parametro('execucao'));
      setCena(parametro('cena'));
      setRaioX(parametro('visao') === 'raio-x');
    }, []),
  );
  const trocarVisao = useCallback((paraRaioX: boolean) => {
    const busca = new URLSearchParams(window.location.search);
    if (paraRaioX) busca.set('visao', 'raio-x');
    else busca.delete('visao');
    const consulta = busca.toString();
    navegar(`/mapa${consulta ? `?${consulta}` : ''}`, true);
  }, []);
  // Replay offline: antes de tocar, o mundo volta ao que era na gravação (os incidentes ativos).
  const [gravacoes, setGravacoes] = useState<Gravacao[]>([]);
  const [replayPronto, setReplayPronto] = useState<string | null>(null);
  useEffect(() => {
    api.gravacoes().then(setGravacoes, () => setGravacoes([]));
  }, []);
  const cabecalho = gravacoes.find((g) => g.nome === gravacao) ?? null;
  useEffect(() => {
    setReplayPronto(null);
    if (!gravacao || !cabecalho) return;
    let cancelado = false;
    (async () => {
      try {
        await simulador.acao('/reset');
        for (const incidente of cabecalho.incidentes ?? []) await simulador.acao(`/incidentes/${incidente}/aplicar`);
      } catch {
        // Sem simulador, o replay toca do mesmo jeito: só o trânsito do mapa não acompanha.
      }
      if (!cancelado) setReplayPronto(gravacao);
    })();
    return () => {
      cancelado = true;
    };
  }, [gravacao, cabecalho]);

  const [cidade, setCidade] = useState<Cidade | null>(null);
  const [rotas, setRotas] = useState<RotaDaJornada[]>([]);
  const [modelo, setModelo] = useState<EstadoDoModelo | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  // Trânsito: a cidade é relida a cada 5 s (o simulador muda o mundo). As rotas dão só a ordem
  // das 9 paradas da linha do tempo; no mapa, o que aparece é o caminho real do robô.
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

  // A geometria (ruas, lotes, construções) só é refeita se a cidade mudar de forma.
  const chave = chaveDaGeometria(cidade);
  const cena3d = useMemo(() => (cidade ? montarCena(cidade) : null), [chave]); // eslint-disable-line react-hooks/exhaustive-deps
  const nos = useMemo(() => new Map((cidade?.nos ?? []).map((n) => [n.id, n])), [cidade]);

  // --- Os caminhos pelas ruas (memorizados por par de lugares) -------------------------------
  const trajetos = useRef(new Map<string, Trajeto>());
  const trajetoEntre = useCallback(
    (de: string, para: string): Trajeto | null => {
      const chaveDoPar = `${de}>${para}`;
      const guardado = trajetos.current.get(chaveDoPar);
      if (guardado) return guardado;
      const a = nos.get(de);
      const b = nos.get(para);
      if (!a || !b || !cidade) return null;
      const t2 = trajeto(caminhoPelasRuas(pontoDaPorta(a), pontoDaPorta(b), cidade.cidade));
      trajetos.current.set(chaveDoPar, t2);
      return t2;
    },
    [nos, cidade],
  );
  const tempoDoTrecho = useCallback(
    (de: string, para: string) => {
      const t2 = trajetoEntre(de, para);
      return t2 ? duracaoDoTrecho(t2.total) : null;
    },
    [trajetoEntre],
  );

  // Tudo o que aparece na tela (o mapa e a conversa) é o que o diretor já exibiu: a pergunta à Ana
  // só aparece quando o robô chega à parada dela. O estado real serve só para responder (o id).
  // No replay ninguém responde.
  const real = useViagem(gravacao ? (replayPronto ? PREFIXO_GRAVACAO + replayPronto : null) : execucao);
  const replay = ehReplay(real.id);
  // Passo a passo: o mapa para em cada balão até o apresentador mandar seguir. A escolha fica guardada.
  const [passoAPasso, setPassoAPasso] = useState(() => localStorage.getItem(CHAVE_PASSO_A_PASSO) !== 'nao');
  useEffect(() => localStorage.setItem(CHAVE_PASSO_A_PASSO, passoAPasso ? 'sim' : 'nao'), [passoAPasso]);
  const nomeDoLugar = useCallback((id: string) => nos.get(id)?.nome ?? null, [nos]);
  const direcao = useDiretor(real, tempoDoTrecho, passoAPasso, nomeDoLugar);
  const telao = useTelao();
  const exibido = direcao.exibido;

  // Responder pela Ana, uma vez por pergunta: a pergunta exibida pelo diretor pode continuar na tela
  // depois de respondida (o mapa está atrás do agente), e há mais de um lugar para responder.
  const respondendo = useRef<string | null>(null);
  const responderPelaAna = useCallback(
    async (texto: string) => {
      const chave = `${real.id}:${exibido.mensagens.filter((m) => m.tipo === 'pergunta').length}`;
      if (!real.id || !real.pergunta || respondendo.current === chave) return;
      respondendo.current = chave;
      try {
        await apiViagem.responder(real.id, texto);
      } catch {
        respondendo.current = null;
      }
    },
    [real.id, real.pergunta, exibido.mensagens],
  );

  // --- Câmera -------------------------------------------------------------------------
  const area = useRef<HTMLDivElement>(null);
  const deck = useRef<DeckGLRef>(null);
  const inicioDoClique = useRef<[number, number] | null>(null);
  const [tamanho, setTamanho] = useState<[number, number]>([0, 0]);
  const [base, setBase] = useState<Visao | null>(null);
  const [visao, setVisao] = useState<Visao | null>(null);
  const [seguir, setSeguir] = useState(true);
  const viagemEmCurso = Boolean(exibido.id && !(exibido.fim && direcao.fila === 0));
  const cameraSeguindo = seguir && viagemEmCurso;

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
        transitionDuration: movimentoReduzido() ? 0 : duracao,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
      }));
    },
    [base],
  );
  const pontoDoNo = useCallback(
    (id: string, z = Z_CHAO): Ponto3 | null => {
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
  const voltarACidade = useCallback(
    (duracao = 900) => {
      if (!base) return;
      // O norte volta para cima pelo menor giro (o mapa pode ter dado voltas com o GPS ou os botões).
      setVisao((v) => ({
        ...base,
        rotationOrbit: v ? v.rotationOrbit - normalizar(v.rotationOrbit) : base.rotationOrbit,
        transitionDuration: movimentoReduzido() ? 0 : duracao,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom', 'rotationX', 'rotationOrbit']),
      }));
    },
    [base],
  );
  const nivel = visao && base ? visao.zoom - base.zoom : 0;
  const giroAtual = Math.round(normalizar(visao?.rotationOrbit ?? 0));
  // Girar e inclinar pelos botões (a câmera fica livre: o seguimento pausa).
  const girar = useCallback((graus: number, inclinacao: number) => {
    setSeguir(false);
    setVisao(
      (v) =>
        v && {
          ...v,
          rotationOrbit: v.rotationOrbit + graus,
          rotationX: Math.min(Math.max(v.rotationX + inclinacao, v.minRotationX ?? 25), v.maxRotationX ?? 88),
          transitionDuration: 400,
          transitionInterpolator: new LinearInterpolator(['rotationOrbit', 'rotationX']),
        },
    );
  }, []);

  // ?parada=N (da tela de abertura): o mapa abre naquela parada.
  // Só uma vez: a cidade é relida a cada 5 s (o trânsito), e a câmera não pode voltar sozinha.
  const paradaDaAbertura = useRef(false);
  useEffect(() => {
    if (paradaDaAbertura.current || !base) return;
    const numero = parametro('parada');
    const alvo = paradasDaJornada(rotas, null).find((p) => String(p.numero) === numero);
    const ponto = alvo && pontoDoNo(alvo.id);
    if (!ponto) return;
    paradaDaAbertura.current = true;
    voar(ponto, ZOOM_SEGUINDO);
  }, [rotas, base, pontoDoNo, voar]);

  const trechoAtual = direcao.trechos.at(-1) ?? null;

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

  // --- O robô e o rastro: o caminho real, trecho a trecho --------------------------------------
  const { robo, rastro, rumo } = useMemo(() => {
    if (!exibido.modo || !cena3d || !direcao.partida) return { robo: null, rastro: null, rumo: null };
    const naCena = ([x, y]: Ponto): Ponto3 => cena3d.ponto(x, y, Z_RUA + 0.3);
    const inicio = nos.get(direcao.partida);
    const pontos: Ponto3[] = inicio ? [naCena(pontoDaPorta(inicio))] : [];
    const tempos: number[] = [0];
    let percorrido = 0;
    let posicao: Ponto3 | null = pontos[0] ?? null;
    let rumo: number | null = null; // graus, no sentido horário a partir do norte da cena
    for (const tr of direcao.trechos) {
      const t2 = trajetoEntre(tr.de, tr.para);
      if (!t2) continue;
      const base0 = tempos.at(-1) ?? 0;
      t2.pontos.slice(1).forEach((p, i) => {
        pontos.push(naCena(p));
        tempos.push(base0 + t2.acumulado[i + 1]);
      });
      const progresso = tr.duracao ? Math.min((agora - tr.inicio) / tr.duracao, 1) : 1;
      const s = suave(Math.max(progresso, 0)) * t2.total;
      percorrido = base0 + s;
      posicao = naCena(pontoNoTrajeto(t2, s));
      // O rumo: de um pouco atrás a um pouco à frente do robô. Parado, fica o da chegada.
      if (t2.total > 0) {
        const fim = Math.min(Math.max(s + 6, 8), t2.total);
        const [a, b] = [naCena(pontoNoTrajeto(t2, Math.max(fim - 8, 0))), naCena(pontoNoTrajeto(t2, fim))];
        if (Math.hypot(b[0] - a[0], b[1] - a[1]) > 0.5) rumo = (Math.atan2(b[0] - a[0], b[1] - a[1]) * 180) / Math.PI;
      }
    }
    const r: Rastro = { pontos, tempos, percorrido };
    return { robo: posicao, rastro: r, rumo };
  }, [exibido.modo, cena3d, direcao.partida, direcao.trechos, agora, nos, trajetoEntre]);

  // --- Câmera de GPS -------------------------------------------------------------------------
  // Durante a viagem, a câmera fica baixa e com o robô no centro, ajustada a cada quadro.
  const quadroDaCamera = useRef(0);
  useEffect(() => {
    if (!cameraSeguindo || !robo || !base) return;
    const passo = Math.min(agora - (quadroDaCamera.current || agora - 16), 500);
    quadroDaCamera.current = agora;
    // Com movimento reduzido, a câmera vai direto, sem deslizar nem girar aos poucos.
    const reduzido = movimentoReduzido();
    const k = reduzido ? 1 : 1 - Math.exp(-Math.max(passo, 0) / TEMPO_DA_CAMERA_MS);
    const kGiro = reduzido ? 1 : 1 - Math.exp(-Math.max(passo, 0) / TEMPO_DO_GIRO_MS);
    const perto = (a: number, b: number) => a + (b - a) * k;
    setVisao((v) => {
      const atual = v ?? base;
      // Visão traseira: o mapa gira para a direção da viagem ficar para cima, pelo menor ângulo,
      // e o alvo fica um pouco à frente do robô (ele aparece no terço de baixo da tela).
      const giroAlvo = rumo == null ? atual.rotationOrbit : SENTIDO_DO_GIRO * rumo;
      const giro = normalizar(atual.rotationOrbit + normalizar(giroAlvo - atual.rotationOrbit) * kGiro);
      const frente = (SENTIDO_DO_GIRO * giro * Math.PI) / 180;
      const alvo = [robo[0] + Math.sin(frente) * AVANCO_DA_CAMERA, robo[1] + Math.cos(frente) * AVANCO_DA_CAMERA];
      return {
        ...atual,
        target: [perto(atual.target[0], alvo[0]), perto(atual.target[1], alvo[1]), 0],
        zoom: perto(atual.zoom, base.zoom + ZOOM_GPS),
        rotationX: perto(atual.rotationX, INCLINACAO_GPS),
        rotationOrbit: giro,
        transitionDuration: 0,
      };
    });
  }, [cameraSeguindo, robo, rumo, base, agora]);

  // Ao fim da viagem (o diretor já mostrou a chegada), a câmera sobe para a cidade inteira, uma vez,
  // e fica livre para o apresentador explorar.
  const fimEnquadrado = useRef<string | null>(null);
  useEffect(() => {
    if (!exibido.id || !exibido.fim || direcao.fila > 0 || fimEnquadrado.current === exibido.id) return;
    fimEnquadrado.current = exibido.id;
    if (seguir) voltarACidade(1800);
  }, [exibido.id, exibido.fim, direcao.fila, seguir, voltarACidade]);

  const [selecionado, setSelecionado] = useState<string | null>(null);
  const chegada = exibido.fim?.apolice && trechoAtual ? pontoDoNo(trechoAtual.para, Z_RUA) : null;

  const listaDeCamadas = useMemo(
    () =>
      cena3d && cidade
        ? camadas({
            cena: cena3d,
            cidade,
            exibido,
            agora,
            raioX,
            selecionado,
            robo,
            rastro,
            chegada,
            escala: telao.escala,
          })
        : [],
    [cena3d, cidade, exibido, agora, raioX, selecionado, robo, rastro, chegada],
  );

  // --- Rótulos em HTML ----------------------------------------------------------------------
  const projetar = useMemo(() => {
    if (!visao || !tamanho[0]) return null;
    const viewport = VISTA.makeViewport({ width: tamanho[0], height: tamanho[1], viewState: visao });
    if (!viewport) return null;
    return (p: Ponto3) => viewport.project(p) as [number, number];
  }, [visao, tamanho]);

  const paradas = useMemo(() => paradasDaJornada(rotas, exibido.rota), [rotas, exibido.rota]);
  const mostrarNomes = raioX || nivel >= NIVEL_DOS_NOMES;
  const rotulos: Rotulo[] = useMemo(() => {
    if (!cena3d || !cidade) return [];
    const lista: Rotulo[] = [];
    const visitadas = new Set(exibido.visitadas);
    for (const b of cena3d.bairros) {
      lista.push({
        id: `bairro-${b.id}`,
        tipo: 'bairro',
        texto: b.nome,
        posicao: [b.centro[0], b.centro[1], 50],
        prioridade: mostrarNomes ? 3 : 1,
        estado: mostrarNomes ? 'esmaecido' : undefined,
        aoClicar: () => voarParaBairro(b.id),
      });
    }
    for (const p of paradas) {
      const atual = p.id === exibido.parada;
      const ponto = pontoDoNo(p.id, Z_RUA + 22);
      if (!ponto || p.numero == null) continue;
      lista.push({
        id: `parada-${p.id}`,
        tipo: 'parada',
        texto: p.nome,
        numero: p.numero,
        posicao: ponto,
        prioridade: atual ? 0.5 : 2,
        estado: atual ? 'atual' : visitadas.has(p.id) ? 'feita' : 'pendente',
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
        posicao: cena3d.ponto(n.x, n.y, Z_CHAO + 76),
        prioridade: 0,
        aoClicar: () => setSelecionado(n.id),
      });
    }
    if (exibido.pedagio) {
      const ponto = pontoDoNo('parada-aprovacao-humana', Z_RUA + 26);
      if (ponto) lista.push({ id: 'pedagio', tipo: 'pedagio', texto: t.pedagio, posicao: ponto, prioridade: 0.4 });
    }
    if (mostrarNomes) {
      const comFarol = new Set(incidentes.map((n) => n.id));
      // No GPS (seguindo o robô), só os nomes dos lugares da viagem: o destino atual e os já visitados.
      const daViagem = cameraSeguindo ? new Set(direcao.trechos.map((x) => x.para)) : null;
      for (const c of cena3d.construcoes) {
        if (c.estilo === 'placa' || comFarol.has(c.no.id)) continue;
        if (daViagem && !daViagem.has(c.no.id) && c.no.id !== selecionado) continue;
        lista.push({
          id: `construcao-${c.no.id}`,
          tipo: 'sistema',
          texto: c.no.nome,
          status: c.no.status,
          posicao: [c.posicao[0], c.posicao[1], c.posicao[2] + 18],
          prioridade: c.no.id === selecionado ? 1 : c.no.status ? 4 : 5,
          aoClicar: () => setSelecionado(c.no.id),
        });
      }
    }
    return lista;
  }, [
    cena3d,
    cidade,
    paradas,
    exibido.parada,
    exibido.visitadas,
    exibido.pedagio,
    mostrarNomes,
    selecionado,
    pontoDoNo,
    voarParaBairro,
    cameraSeguindo,
    direcao.trechos,
  ]);

  // --- Barra de viagem ----------------------------------------------------------------
  const preset: { modo?: string; incidente?: string } = presetDaCena(cena) ?? {};
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
      // Os incidentes ativos dizem qual é o caso da viagem: é por ele que o placar confere as regras.
      const incidentes = await incidentesAtivos();
      setIncidentesDaViagem(incidentes);
      const pedido =
        modeloEscolhido === ROTEIRO
          ? { modo, canal, provedor: ROTEIRO, incidentes }
          : { modo, canal, modelo: modeloEscolhido, incidentes };
      const { id } = await apiViagem.iniciar(pedido);
      setSeguir(true);
      voltarACidade();
      const busca = new URLSearchParams({ execucao: id });
      if (cena) busca.set('cena', cena);
      if (raioX) busca.set('visao', 'raio-x');
      navegar(`/mapa?${busca.toString()}`);
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

  // A gaveta do apresentador: tecla P (fora de campos de texto) ou o botão da barra.
  const [apresentador, setApresentador] = useState(false);
  useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      const alvo = evento.target as HTMLElement;
      if (alvo.closest('input, textarea, [contenteditable="true"]')) return;
      if (evento.key === 'p' || evento.key === 'P') setApresentador((a) => !a);
    };
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, []);

  // Seguir com a jornada pelo teclado: Espaço, Enter ou →, quando o robô espera num balão.
  const { aguardando, seguir: seguirJornada } = direcao;
  useEffect(() => {
    if (!aguardando) return;
    const aoTeclar = (evento: KeyboardEvent) => {
      const alvo = evento.target as HTMLElement;
      if (alvo.closest('input, textarea, select, button, [role="tab"], [contenteditable="true"]')) return;
      if (evento.key === ' ' || evento.key === 'Enter' || evento.key === 'ArrowRight') {
        evento.preventDefault();
        seguirJornada();
      }
    };
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, [aguardando, seguirJornada]);

  const [incidentesDaViagem, setIncidentesDaViagem] = useState<string[]>([]);
  const [gravada, setGravada] = useState<string | null>(null);
  useEffect(() => setGravada(null), [real.id]);
  async function gravarViagem() {
    if (!real.id) return;
    try {
      const salva = await gravar({ execucao: real.id, cena, incidentes: incidentesDaViagem });
      setGravada(salva.nome);
      api.gravacoes().then(setGravacoes, () => undefined);
    } catch {
      setErro(t.erroGravar);
    }
  }

  const emAndamento = Boolean(real.id && !real.fim && !replay);
  const ultimoIncidente = exibido.incidentes.at(-1);
  const ultimoRecalculo = exibido.recalculos.at(-1);
  const noSelecionado = selecionado ? nos.get(selecionado) : undefined;

  return (
    <section
      className="mapa"
      aria-labelledby="titulo-mapa"
      // Estado observável para os testes e2e (o mapa em si é um canvas).
      data-execucao={real.id ?? ''}
      data-parada={exibido.parada ?? ''}
      data-visitadas={exibido.visitadas.length}
      data-lugares-visitados={direcao.trechos.length}
      data-nomes={mostrarNomes ? 'sim' : 'nao'}
      data-fila={direcao.fila}
      data-camera={cameraSeguindo ? 'seguindo' : 'livre'}
      data-nivel={nivel.toFixed(1)}
      data-giro={giroAtual}
      data-balao={direcao.balao?.tipo ?? ''}
      data-aguardando={direcao.aguardando ? 'sim' : 'nao'}
    >
      <div className="mapa__barra">
        <h1 id="titulo-mapa" className="mapa__titulo">
          {raioX ? mensagens.raioX.raioX : t.titulo}
        </h1>
        <ContentSwitcher
          className="mapa__visao"
          size="md"
          selectedIndex={raioX ? 1 : 0}
          onChange={({ index }: { index?: number }) => trocarVisao(index === 1)}
          aria-label={mensagens.raioX.alternar}
        >
          <Switch name="mapa" text={mensagens.raioX.mapa} />
          <Switch name="raio-x" text={mensagens.raioX.raioX} />
        </ContentSwitcher>
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
        <Toggle
          id="passo-a-passo"
          size="sm"
          className="mapa__passo-a-passo"
          labelText={t.passoAPasso}
          labelA={t.passoAPasso}
          labelB={t.passoAPasso}
          hideLabel
          title={t.passoAPassoAjuda}
          toggled={passoAPasso}
          onToggle={setPassoAPasso}
        />
        <Button
          id="abrir-apresentador"
          kind={apresentador ? 'secondary' : 'ghost'}
          size="md"
          renderIcon={PresentationFile}
          onClick={() => setApresentador((a) => !a)}
          aria-pressed={apresentador}
        >
          {mensagens.apresentador.abrir}
        </Button>
        {cena && (
          <div className="mapa__cena">
            <Tag type="warm-gray" size="md">
              {t.cena(cena)}
            </Tag>
            <Button
              id="bastidores-da-cena"
              kind="ghost"
              size="md"
              renderIcon={Book}
              onClick={() =>
                abrirBastidores({
                  capitulo: CAPITULO_DAS_CENAS,
                  ancora: `cena-${cena}`,
                  titulo: mensagens.bastidores.cena(cena, mensagens.apresentador.nomes[cena] ?? ''),
                })
              }
            >
              {mensagens.bastidores.daCena}
            </Button>
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
                if ((e.target as HTMLElement).closest('.rotulo, .balao')) return; // o rótulo e o balão tratam o próprio clique
                const [x0, y0] = inicioDoClique.current ?? [e.clientX, e.clientY];
                if (Math.hypot(e.clientX - x0, e.clientY - y0) > 5) return; // foi arrasto
                const caixa = e.currentTarget.getBoundingClientRect();
                const info = deck.current?.pickObject({
                  x: e.clientX - caixa.left,
                  y: e.clientY - caixa.top,
                  radius: 4,
                  layerIds: CAMADAS_CLICAVEIS,
                });
                const lugar = (info?.object as { no?: NoDoMapa } | undefined)?.no;
                if (lugar) setSelecionado(lugar.id);
              }}
            >
              <DeckGL
                ref={deck}
                useDevicePixels={telao.ligado ? 1.5 : true}
                views={VISTA}
                viewState={visao}
                onViewStateChange={({ viewState, interactionState }) => {
                  // O apresentador mexeu na câmera: o seguimento pausa até ele religar "Seguir o agente".
                  const i = interactionState;
                  if (cameraSeguindo && (i.isDragging || i.isPanning || i.isZooming || i.isRotating)) setSeguir(false);
                  setVisao(viewState as Visao);
                }}
                controller={CONTROLE}
                effects={[LUZ]}
                layers={listaDeCamadas}
                getCursor={({ isHovering, isDragging }) =>
                  isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab'
                }
                getTooltip={({ object }) => {
                  const lugar = (object as { no?: NoDoMapa } | null)?.no;
                  return lugar ? { text: `${lugar.nome}\n${lugar.tipo_exibicao}` } : null;
                }}
              />
              {projetar && (
                <Rotulos
                  rotulos={rotulos}
                  projetar={projetar}
                  largura={tamanho[0]}
                  altura={tamanho[1] - ALTURA_DA_LINHA_DO_TEMPO_PX * telao.escala}
                  reservado={espacoDoRobo(robo, projetar, telao.escala)}
                  escala={telao.escala}
                />
              )}
              {projetar && robo && direcao.balao && (
                <Balao
                  balao={direcao.balao}
                  posicao={projetar([robo[0], robo[1], Z_RUA + 0.3 + ALTURA_DO_ROBO])}
                  largura={tamanho[0]}
                  escala={telao.escala}
                  aguardando={direcao.aguardando}
                  aoSeguir={direcao.seguir}
                />
              )}
            </div>
          )}

          <Apresentador
            aberto={apresentador}
            aoFechar={() => setApresentador(false)}
            cenaAtual={cena}
            real={{ ...exibido, id: real.id }}
            aoResponder={responderPelaAna}
            gravacoes={gravacoesPorCena(gravacoes)}
            aguardando={direcao.aguardando}
            aoSeguir={direcao.seguir}
          />

          <div className="mapa__estado">
            {replay && cabecalho && (
              <Tag type="purple" size="md" title={t.replayAjuda} className="mapa__selo-replay">
                {t.replay(
                  new Date(cabecalho.gravado_em).toLocaleDateString('pt-BR'),
                  t.barra.modelo(cabecalho.modelo),
                )}
              </Tag>
            )}
            {real.fim && !replay && real.id && (
              <Button kind="tertiary" size="sm" onClick={gravarViagem} disabled={Boolean(gravada)}>
                {gravada ? t.gravada(gravada) : t.gravar}
              </Button>
            )}
            {real.id && !replay && (
              <Tag type={direcao.aguardando ? 'blue' : direcao.fila > 0 ? 'warm-gray' : 'green'} size="md">
                {direcao.aguardando
                  ? t.aguardando
                  : direcao.fila > 0
                    ? t.reproduzindo(direcao.fila)
                    : real.fim
                      ? t.encerrada
                      : t.aoVivo}
              </Tag>
            )}
            {direcao.fila > 3 && (
              <Button kind="ghost" size="sm" onClick={direcao.pularParaOFim}>
                {t.pularParaOFim}
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
                title={t.recalculo}
                subtitle={`${ultimoRecalculo.motivo} ${t.regra}: ${ultimoRecalculo.regra}`}
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
              onClick={() => {
                setSeguir(false);
                setVisao((v) => v && { ...v, zoom: v.zoom + 0.5, transitionDuration: 300 });
              }}
            >
              <Add />
            </IconButton>
            <IconButton
              kind="secondary"
              label={t.afastar}
              onClick={() => {
                setSeguir(false);
                setVisao((v) => v && { ...v, zoom: v.zoom - 0.5, transitionDuration: 300 });
              }}
            >
              <Subtract />
            </IconButton>
            <IconButton kind="secondary" label={t.girarEsquerda} onClick={() => girar(-PASSO_DO_GIRO, 0)}>
              <RotateCounterclockwise />
            </IconButton>
            <IconButton kind="secondary" label={t.girarDireita} onClick={() => girar(PASSO_DO_GIRO, 0)}>
              <RotateClockwise />
            </IconButton>
            <IconButton kind="secondary" label={t.inclinarMais} onClick={() => girar(0, -PASSO_DA_INCLINACAO)}>
              <ChevronDown />
            </IconButton>
            <IconButton kind="secondary" label={t.inclinarMenos} onClick={() => girar(0, PASSO_DA_INCLINACAO)}>
              <ChevronUp />
            </IconButton>
            <IconButton
              kind="secondary"
              label={t.norte(giroAtual)}
              className="mapa__bussola"
              onClick={() => girar(-giroAtual, 0)}
            >
              <Compass style={{ transform: `rotate(${-giroAtual}deg)` }} />
            </IconButton>
            <IconButton kind="secondary" label={t.enquadrar} onClick={() => voltarACidade()}>
              <ZoomFit />
            </IconButton>
          </div>

          <LinhaDoTempo paradas={paradas} viagem={exibido} />
        </div>

        {raioX ? (
          <PainelRaioX
            viagem={exibido}
            conversa={replay ? { ...exibido, pergunta: null } : exibido}
            nos={nos}
            aoResponder={responderPelaAna}
            aoEscolherNo={(id) => {
              setSelecionado(id);
              const ponto = pontoDoNo(id);
              if (ponto) voar(ponto, ZOOM_SEGUINDO + 0.2);
            }}
          />
        ) : (
          <Conversa
            viagem={replay ? { ...exibido, pergunta: null } : exibido}
            aoResponder={responderPelaAna}
          />
        )}
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
              if (vizinho) voar(vizinho, ZOOM_SEGUINDO + 0.2);
            }}
          />
        </PainelLateral>
      )}
    </section>
  );
}
