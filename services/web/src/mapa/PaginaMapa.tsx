// Modo Mapa: a cidade do banco (o grafo) e a viagem do agente (os eventos), lado a lado.

import { Add, Play, Subtract, ZoomFit } from '@carbon/icons-react';
import { Button, Dropdown, IconButton, InlineNotification, Tag, Toggle } from '@carbon/react';
import { LinearInterpolator, OrthographicView } from '@deck.gl/core';
import DeckGL, { type DeckGLRef } from '@deck.gl/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { aplicarIncidente, api, viagem as apiViagem } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import { navegar, parametro, useMudancaDeEndereco } from '../navegacao';
import { PainelLateral } from '../status/Painel';
import type { Cidade, EstadoDoModelo, NoDoMapa, Ponto, RotaDaJornada } from '../tipos';
import { camadas, DURACAO_DO_PULSO_MS, NIVEL, rotulosQueCabem } from './camadas';
import { CartaoDeRotas, Conversa, DetalheDoNo, Legenda } from './Paineis';
import { useViagem } from './viagem';

const t = mensagens.mapa;
const INTERVALO_TRANSITO_MS = 5000;
// Uma só instância: recriar a vista a cada quadro reinicia o controle e engole os cliques.
const VISTA = new OrthographicView({ id: 'cidade', flipY: true });
const CONTROLE = { dragRotate: false, scrollZoom: { speed: 0.01, smooth: true } };

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
  transitionDuration?: number;
  transitionInterpolator?: LinearInterpolator;
}

function enquadramento(largura: number, altura: number, cidade: Cidade | null): Visao {
  const mundo = cidade?.mundo ?? { largura: 1000, altura: 700 };
  const escala = Math.min(largura / mundo.largura, altura / mundo.altura) * 0.92;
  return { target: [mundo.largura / 2, mundo.altura / 2, 0], zoom: Math.log2(Math.max(escala, 0.05)) };
}

export function PaginaMapa() {
  const [execucao, setExecucao] = useState<string | null>(() => parametro('execucao'));
  const [cena, setCena] = useState<string | null>(() => parametro('cena'));
  useMudancaDeEndereco(
    useCallback(() => {
      setExecucao(parametro('execucao'));
      setCena(parametro('cena'));
    }, []),
  );
  const viagem = useViagem(execucao);

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

  // --- Câmera -------------------------------------------------------------------------
  const area = useRef<HTMLDivElement>(null);
  const deck = useRef<DeckGLRef>(null);
  const inicioDoClique = useRef<[number, number] | null>(null);
  const [base, setBase] = useState<Visao | null>(null);
  const [visao, setVisao] = useState<Visao>({ target: [500, 350, 0], zoom: 0 });
  const [seguir, setSeguir] = useState(true);

  useEffect(() => {
    if (!area.current || !cidade || base) return;
    const inicial = enquadramento(area.current.clientWidth, area.current.clientHeight, cidade);
    setBase(inicial);
    setVisao(inicial);
  }, [cidade, base]);

  const nos = useMemo(() => new Map((cidade?.nos ?? []).map((n) => [n.id, n])), [cidade]);
  const voar = useCallback(
    (ponto: Ponto, zoomRelativo = 1.2) => {
      if (!base) return;
      setVisao((atual) => ({
        target: [ponto[0], ponto[1], 0],
        zoom: Math.max(atual.zoom, base.zoom + zoomRelativo),
        transitionDuration: 600,
        transitionInterpolator: new LinearInterpolator(['target', 'zoom']),
      }));
    },
    [base],
  );

  // ?parada=N (da tela de abertura): o mapa abre naquela parada.
  useEffect(() => {
    const numero = parametro('parada');
    const rota = rotas.find((r) => r.id === 'rota-economica') ?? rotas[0];
    const alvo = rota?.paradas.find((p) => String(p.numero) === numero);
    const no = alvo && nos.get(alvo.id);
    if (no && base) voar([no.x, no.y], 1.4);
  }, [rotas, nos, base, voar]);

  // --- O robô: anda só quando chega um step.started (evento real) ---------------------
  const posicaoDoRobo: Ponto | null = useMemo(() => {
    const no: NoDoMapa | undefined =
      (viagem.parada && nos.get(viagem.parada)) ||
      (viagem.modo ? nos.get(PONTO_DE_PARTIDA[viagem.canal ?? 'app'] ?? 'canal-app') : undefined);
    return no ? [no.x, no.y] : null;
  }, [viagem.parada, viagem.modo, viagem.canal, nos]);

  useEffect(() => {
    if (seguir && posicaoDoRobo && viagem.parada) voar(posicaoDoRobo);
  }, [seguir, posicaoDoRobo, viagem.parada, voar]);

  // --- Animação: o rastro da rota e os pulsos -----------------------------------------
  // O relógio só corre enquanto há o que animar: uma rota planejada ou um pulso recente.
  const [relogio, setRelogio] = useState({ tempo: 0, agora: performance.now() });
  const ultimoPulso = viagem.pulsos.at(-1)?.quando ?? 0;
  useEffect(() => {
    if (!viagem.rota && performance.now() - ultimoPulso > DURACAO_DO_PULSO_MS) return;
    let quadro = 0;
    const passo = (agora: number) => {
      setRelogio({ tempo: agora / 1000, agora });
      if (viagem.rota || agora - ultimoPulso < DURACAO_DO_PULSO_MS) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [viagem.rota, ultimoPulso]);

  const [destacada, setDestacada] = useState<string | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);

  // Recalcula os nomes que cabem só quando o zoom muda (em passos de 0,1).
  const zoomArredondado = Math.round(visao.zoom * 10) / 10;
  const nomesVisiveis = useMemo(
    () => rotulosQueCabem(cidade?.nos ?? [], zoomArredondado),
    [cidade, zoomArredondado],
  );

  const listaDeCamadas = useMemo(
    () =>
      cidade && base
        ? camadas({
            cidade,
            rotas,
            viagem,
            nivel: visao.zoom - base.zoom,
            tempo: relogio.tempo,
            agora: relogio.agora,
            destacada,
            posicaoDoRobo,
            nomesVisiveis,
          })
        : [],
    [cidade, rotas, viagem, visao.zoom, base, relogio, destacada, posicaoDoRobo, nomesVisiveis],
  );

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

  const emAndamento = Boolean(viagem.id && !viagem.fim);
  const ultimoIncidente = viagem.incidentes.at(-1);
  const ultimoRecalculo = viagem.recalculos.at(-1);
  const noSelecionado = selecionado ? nos.get(selecionado) : undefined;

  return (
    <section
      className="mapa"
      aria-labelledby="titulo-mapa"
      // Estado observável para os testes e2e (o mapa em si é um canvas).
      data-execucao={viagem.id ?? ''}
      data-parada={viagem.parada ?? ''}
      data-visitadas={viagem.visitadas.length}
      data-nomes={base && visao.zoom - base.zoom >= NIVEL.nomes ? nomesVisiveis.length : 0}
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
          {cidade && base && (
            // O clique é tratado aqui, com pickObject síncrono: o relógio da animação re-renderiza
            // o React a cada quadro e o onClick do deck.gl (picking assíncrono) se perde nisso.
            <div
              className="mapa__tela"
              onPointerDown={(e) => (inicioDoClique.current = [e.clientX, e.clientY])}
              onClick={(e) => {
                const [x0, y0] = inicioDoClique.current ?? [e.clientX, e.clientY];
                if (Math.hypot(e.clientX - x0, e.clientY - y0) > 5) return; // foi arrasto
                const caixa = e.currentTarget.getBoundingClientRect();
                const info = deck.current?.pickObject({
                  x: e.clientX - caixa.left,
                  y: e.clientY - caixa.top,
                  radius: 4,
                  layerIds: ['paradas', 'nos'],
                });
                if (info?.object) setSelecionado((info.object as { id: string }).id);
              }}
            >
              <DeckGL
                ref={deck}
                views={VISTA}
                viewState={visao}
                onViewStateChange={({ viewState }) => setVisao(viewState as Visao)}
                controller={CONTROLE}
                layers={listaDeCamadas}
                getCursor={({ isHovering }) => (isHovering ? 'pointer' : 'grab')}
                getTooltip={({ object, layer }) =>
                  object && layer?.id === 'nos'
                    ? { text: `${(object as NoDoMapa).nome}\n${(object as NoDoMapa).tipo_exibicao}` }
                    : null
                }
              />
            </div>
          )}

          <CartaoDeRotas rotas={rotas} ativa={viagem.rota} aoDestacar={setDestacada} />
          <Legenda />

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
            {viagem.motivoDaRota && !ultimoRecalculo && (
              <InlineNotification
                kind="info"
                lowContrast
                hideCloseButton
                title={t.rotaEscolhida}
                subtitle={viagem.motivoDaRota}
              />
            )}
            {viagem.fim && (
              <InlineNotification
                kind={viagem.fim.apolice ? 'success' : viagem.fim.status === 'concluida' ? 'info' : 'error'}
                lowContrast
                hideCloseButton
                title={viagem.fim.apolice ? t.fim.apolice(viagem.fim.apolice) : t.fim.status(viagem.fim.status)}
                subtitle={t.fim.detalhe(viagem.fim.duracao, viagem.fim.custo, viagem.modelo)}
              />
            )}
          </div>

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
              onClick={() => setVisao((v) => ({ ...v, zoom: v.zoom + 0.5, transitionDuration: 300 }))}
            >
              <Add />
            </IconButton>
            <IconButton
              kind="secondary"
              label={t.afastar}
              onClick={() => setVisao((v) => ({ ...v, zoom: v.zoom - 0.5, transitionDuration: 300 }))}
            >
              <Subtract />
            </IconButton>
            <IconButton
              kind="secondary"
              label={t.enquadrar}
              onClick={() => base && setVisao({ ...base, transitionDuration: 500 })}
            >
              <ZoomFit />
            </IconButton>
          </div>
        </div>

        <Conversa
          viagem={viagem}
          aoResponder={(texto) => apiViagem.responder(viagem.id!, texto).then(() => undefined)}
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
              const vizinho = nos.get(id);
              if (vizinho) voar([vizinho.x, vizinho.y], 1.6);
            }}
          />
        </PainelLateral>
      )}
    </section>
  );
}
