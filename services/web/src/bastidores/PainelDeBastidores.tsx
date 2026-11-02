// Os bastidores sem sair da demo: o capítulo abre num painel lateral, por cima da tela atual.
// É o próprio site de documentação (mesma origem), aberto na seção certa. A viagem continua por baixo.

import { Close, Launch } from '@carbon/icons-react';
import { IconButton } from '@carbon/react';
import { useEffect, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';

const t = mensagens.bastidores;
const EVENTO = 'bussola:bastidores';

export interface DestinoDeBastidores {
  capitulo: string; // ex.: 04-bastidores-das-cenas
  ancora?: string; // ex.: cena-6
  titulo: string;
}

export const enderecoDosBastidores = (d: DestinoDeBastidores) =>
  `/bastidores/${d.capitulo}/${d.ancora ? `#${d.ancora}` : ''}`;

// Qualquer tela abre os bastidores por aqui: um só painel, montado no App.
export function abrirBastidores(destino: DestinoDeBastidores) {
  window.dispatchEvent(new CustomEvent<DestinoDeBastidores>(EVENTO, { detail: destino }));
}

export function PainelDeBastidores() {
  const [destino, setDestino] = useState<DestinoDeBastidores | null>(null);

  useEffect(() => {
    const aoAbrir = (evento: Event) => setDestino((evento as CustomEvent<DestinoDeBastidores>).detail);
    window.addEventListener(EVENTO, aoAbrir);
    return () => window.removeEventListener(EVENTO, aoAbrir);
  }, []);

  useEffect(() => {
    if (!destino) return;
    const aoTeclar = (evento: KeyboardEvent) => evento.key === 'Escape' && setDestino(null);
    window.addEventListener('keydown', aoTeclar);
    return () => window.removeEventListener('keydown', aoTeclar);
  }, [destino]);

  if (!destino) return null;
  const endereco = enderecoDosBastidores(destino);
  return (
    <aside className="bastidores" aria-label={t.rotulo(destino.titulo)}>
      <header className="bastidores__cabecalho">
        <div>
          <span className="bastidores__tipo">{t.tipo}</span>
          <h2 className="bastidores__titulo">{destino.titulo}</h2>
        </div>
        <div className="bastidores__acoes">
          <IconButton kind="ghost" label={t.novaAba} align="bottom" href={endereco} target="_blank" rel="noopener">
            <Launch />
          </IconButton>
          <IconButton kind="ghost" label={t.fechar} align="bottom-end" onClick={() => setDestino(null)}>
            <Close />
          </IconButton>
        </div>
      </header>
      {/* key: trocar de destino recarrega o iframe já na âncora certa. */}
      <iframe key={endereco} className="bastidores__site" src={endereco} title={destino.titulo} />
    </aside>
  );
}
