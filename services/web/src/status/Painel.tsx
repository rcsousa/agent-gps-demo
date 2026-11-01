// Painel lateral de detalhe. A tabela continua visível; Esc ou o X fecham.

import { Close } from '@carbon/icons-react';
import { IconButton, Layer } from '@carbon/react';
import { type ReactNode, useEffect, useRef } from 'react';

import { mensagens } from '../mensagens/pt-BR';

export function PainelLateral(props: { tipo: string; titulo: string; aoFechar: () => void; children: ReactNode }) {
  const titulo = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    titulo.current?.focus();
  }, [props.titulo]);

  useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') props.aoFechar();
    };
    document.addEventListener('keydown', aoTeclar);
    return () => document.removeEventListener('keydown', aoTeclar);
  }, [props]);

  return (
    <aside className="painel" aria-labelledby="painel-titulo">
      <Layer>
        <header className="painel__cabecalho">
          <div>
            <span className="painel__tipo">{props.tipo}</span>
            <h2 id="painel-titulo" ref={titulo} tabIndex={-1} className="painel__titulo">
              {props.titulo}
            </h2>
          </div>
          <IconButton kind="ghost" label={mensagens.painel.fechar} align="left" onClick={props.aoFechar}>
            <Close />
          </IconButton>
        </header>
        <div className="painel__corpo">{props.children}</div>
      </Layer>
    </aside>
  );
}
