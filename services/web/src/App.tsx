import { Content, Header, HeaderMenuItem, HeaderName, HeaderNavigation, Theme } from '@carbon/react';

import { SimboloBussola } from './componentes/SimboloBussola';
import { mensagens } from './mensagens/pt-BR';
import { PaginaStatus } from './status/PaginaStatus';

export function App() {
  return (
    <Theme theme="g100">
      <Header aria-label={mensagens.marca.nome}>
        <HeaderName href="/" prefix="">
          <span className="marca">
            <SimboloBussola className="marca__simbolo" />
            <span>
              {mensagens.marca.prefixo} <strong className="marca__nome">{mensagens.marca.nome}</strong>
            </span>
          </span>
        </HeaderName>
        <HeaderNavigation aria-label={mensagens.navegacao.rotulo}>
          <HeaderMenuItem href="/status" isActive>
            {mensagens.navegacao.status}
          </HeaderMenuItem>
          <HeaderMenuItem href="/bastidores/">{mensagens.navegacao.bastidores}</HeaderMenuItem>
        </HeaderNavigation>
      </Header>
      <Content className="pagina">
        <PaginaStatus />
      </Content>
    </Theme>
  );
}
