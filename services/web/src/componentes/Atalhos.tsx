// O cartão de atalhos de teclado (tecla ?), e os atalhos globais: T liga o modo telão.

import { Modal } from '@carbon/react';
import { useEffect, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';
import { alternarTelao } from '../telao';

const t = mensagens.atalhos;

export function Atalhos() {
  const [aberto, setAberto] = useState(false);
  useEffect(() => {
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') return setAberto(false);
      const alvo = evento.target as HTMLElement;
      if (alvo.closest('input, textarea, select, [contenteditable="true"]')) return;
      if (evento.ctrlKey || evento.metaKey || evento.altKey) return;
      if (evento.key === '?') setAberto((a) => !a);
      else if (evento.key === 't' || evento.key === 'T') alternarTelao();
    };
    // Na captura: o tooltip do botão "Fechar" consumiria o primeiro Esc.
    window.addEventListener('keydown', aoTeclar, true);
    return () => window.removeEventListener('keydown', aoTeclar, true);
  }, []);
  return (
    <Modal
      open={aberto}
      passiveModal
      modalHeading={t.titulo}
      closeButtonLabel={t.fechar}
      onRequestClose={() => setAberto(false)}
      size="sm"
      className="atalhos"
    >
      <dl className="atalhos__lista">
        {t.lista.map(([teclas, acao]) => (
          <div key={teclas}>
            <dt>
              {teclas.split(' / ').map((tecla) => (
                <kbd key={tecla}>{tecla}</kbd>
              ))}
            </dt>
            <dd>{acao}</dd>
          </div>
        ))}
      </dl>
    </Modal>
  );
}
