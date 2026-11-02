// Tela de abertura: o infográfico como grande navegador da demo (deep zoom + áreas clicáveis).

import { Add, ArrowRight, Subtract, ZoomFit } from '@carbon/icons-react';
import { Button, IconButton, InlineNotification } from '@carbon/react';
import OpenSeadragon from 'openseadragon';
import { useCallback, useEffect, useRef, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';
import { abrirBastidores } from '../bastidores/PainelDeBastidores';
import { navegar } from '../navegacao';
import dados from './hotspots.json';

const t = mensagens.abertura;

type Destino =
  | { tipo: 'mapa'; cena?: number; parada?: number; visao?: 'raio-x' }
  | { tipo: 'bastidores'; capitulo: string; ancora?: string }
  | { tipo: 'em-breve'; fase: number };

interface Area {
  id: string;
  rotulo: string;
  descricao: string;
  x: number;
  y: number;
  largura: number;
  altura: number;
  destino: Destino;
}

const AREAS = dados.areas as Area[];
const PROPORCAO = dados.altura / dados.largura;

function caminhoDe(destino: Destino): string | null {
  if (destino.tipo === 'bastidores' || destino.tipo === 'em-breve') return null;
  const busca = new URLSearchParams();
  if (destino.cena) busca.set('cena', String(destino.cena));
  if (destino.parada) busca.set('parada', String(destino.parada));
  if (destino.visao) busca.set('visao', destino.visao);
  return `/mapa${busca.size ? `?${busca}` : ''}`;
}

interface Retangulo {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function Abertura() {
  const recipiente = useRef<HTMLDivElement>(null);
  const visor = useRef<OpenSeadragon.Viewer | null>(null);
  const [retangulos, setRetangulos] = useState<Record<string, Retangulo>>({});
  const [ativa, setAtiva] = useState<string | null>(null);
  const [emBreve, setEmBreve] = useState(false);

  // Cada área acompanha o pan e o zoom: coordenadas do infográfico -> pixels da tela.
  const reposicionar = useCallback(() => {
    const v = visor.current;
    if (!v || !v.world.getItemCount()) return;
    const novos: Record<string, Retangulo> = {};
    for (const a of AREAS) {
      const r = v.viewport.viewportToViewerElementRectangle(
        new OpenSeadragon.Rect(a.x / 100, (a.y / 100) * PROPORCAO, a.largura / 100, (a.altura / 100) * PROPORCAO),
      );
      novos[a.id] = { left: r.x, top: r.y, width: r.width, height: r.height };
    }
    setRetangulos(novos);
  }, []);

  useEffect(() => {
    if (!recipiente.current) return;
    const v = OpenSeadragon({
      element: recipiente.current,
      tileSources: '/abertura/infografico.dzi',
      showNavigationControl: false,
      gestureSettingsMouse: { clickToZoom: false, dblClickToZoom: true },
      visibilityRatio: 0.6,
      minZoomImageRatio: 0.5,
      maxZoomPixelRatio: 2,
      animationTime: 0.4,
    });
    visor.current = v;
    v.addHandler('open', reposicionar);
    v.addHandler('animation', reposicionar);
    v.addHandler('resize', reposicionar);
    return () => {
      v.destroy();
      visor.current = null;
    };
  }, [reposicionar]);

  const abrir = useCallback((area: Area) => {
    if (area.destino.tipo === 'bastidores') {
      // O capítulo abre ao lado, sem sair do infográfico.
      abrirBastidores({ capitulo: area.destino.capitulo, ancora: area.destino.ancora, titulo: area.rotulo });
      return;
    }
    const destino = caminhoDe(area.destino);
    if (destino) navegar(destino);
    else setEmBreve(true);
  }, []);

  // Atalhos do apresentador: Enter inicia, M mapa, S status, B bastidores.
  useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      const alvo = evento.target as HTMLElement;
      if (alvo.closest('input, textarea, button, a') || evento.ctrlKey || evento.metaKey || evento.altKey) return;
      const tecla = evento.key.toLowerCase();
      if (tecla === 'enter' || tecla === 'm') navegar('/mapa');
      if (tecla === 's') navegar('/status');
      if (tecla === 'b') navegar('/bastidores/');
    };
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, []);

  const area = AREAS.find((a) => a.id === ativa);
  const r = area ? retangulos[area.id] : undefined;

  return (
    <section className="abertura" aria-label={t.rotulo}>
      <h1 className="cds--visually-hidden">{t.rotulo}</h1>
      <div ref={recipiente} className="abertura__visor" />
      <div className="abertura__areas">
        {AREAS.map((a) => {
          const ret = retangulos[a.id];
          if (!ret) return null;
          return (
            <button
              key={a.id}
              type="button"
              className={`abertura__area${ativa === a.id ? ' abertura__area--ativa' : ''}`}
              style={ret}
              aria-label={`${a.rotulo}. ${a.descricao}`}
              onMouseEnter={() => setAtiva(a.id)}
              onMouseLeave={() => setAtiva((atual) => (atual === a.id ? null : atual))}
              onFocus={() => setAtiva(a.id)}
              onBlur={() => setAtiva((atual) => (atual === a.id ? null : atual))}
              onClick={() => abrir(a)}
            />
          );
        })}
        {area && r && (
          <div
            className="abertura__dica"
            role="tooltip"
            style={{ left: r.left + r.width / 2, top: Math.max(r.top - 8, 8) }}
          >
            <strong>{area.rotulo}</strong>
            <span>{area.descricao}</span>
          </div>
        )}
      </div>

      <div className="abertura__controles">
        <IconButton kind="secondary" label={t.aproximar} onClick={() => visor.current?.viewport.zoomBy(1.4)}>
          <Add />
        </IconButton>
        <IconButton kind="secondary" label={t.afastar} onClick={() => visor.current?.viewport.zoomBy(1 / 1.4)}>
          <Subtract />
        </IconButton>
        <IconButton kind="secondary" label={t.enquadrar} onClick={() => visor.current?.viewport.goHome()}>
          <ZoomFit />
        </IconButton>
      </div>

      <div className="abertura__iniciar">
        {emBreve && (
          <InlineNotification
            kind="info"
            lowContrast
            title={t.emBreve}
            subtitle={t.emBreveDetalhe}
            onClose={() => setEmBreve(false)}
          />
        )}
        <span className="abertura__atalhos">{t.atalhos}</span>
        <Button size="lg" renderIcon={ArrowRight} onClick={() => navegar('/mapa')}>
          {t.iniciar}
        </Button>
      </div>
    </section>
  );
}
