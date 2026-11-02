import { Content, Header, HeaderMenuItem, HeaderName, HeaderNavigation, Theme } from '@carbon/react';

import { Abertura } from './abertura/Abertura';
import { SimboloBussola } from './componentes/SimboloBussola';
import { PaginaMapa } from './mapa/PaginaMapa';
import { mensagens } from './mensagens/pt-BR';
import { aoClicarLink, usePagina } from './navegacao';
import { PaginaStatus } from './status/PaginaStatus';

export function App() {
  const pagina = usePagina();
  const t = mensagens.navegacao;
  return (
    <Theme theme="g100">
      <Header aria-label={mensagens.marca.nome}>
        <HeaderName href="/" prefix="" onClick={aoClicarLink('/')}>
          <span className="marca">
            <SimboloBussola className="marca__simbolo" />
            <span>
              {mensagens.marca.prefixo} <strong className="marca__nome">{mensagens.marca.nome}</strong>
            </span>
          </span>
        </HeaderName>
        <HeaderNavigation aria-label={t.rotulo}>
          <HeaderMenuItem href="/mapa" isActive={pagina === 'mapa'} onClick={aoClicarLink('/mapa')}>
            {t.mapa}
          </HeaderMenuItem>
          <HeaderMenuItem href="/status" isActive={pagina === 'status'} onClick={aoClicarLink('/status')}>
            {t.status}
          </HeaderMenuItem>
          <HeaderMenuItem href="/bastidores/">{t.bastidores}</HeaderMenuItem>
        </HeaderNavigation>
      </Header>
      {pagina === 'abertura' && (
        <main className="pagina-cheia">
          <Abertura />
        </main>
      )}
      {pagina === 'mapa' && (
        <main className="pagina-cheia">
          <PaginaMapa />
        </main>
      )}
      {pagina === 'status' && (
        <Content className="pagina">
          <PaginaStatus />
        </Content>
      )}
    </Theme>
  );
}
