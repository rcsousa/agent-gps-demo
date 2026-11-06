import {
  Content,
  Header,
  HeaderGlobalAction,
  HeaderGlobalBar,
  HeaderMenuItem,
  HeaderName,
  HeaderNavigation,
  Theme,
} from '@carbon/react';
import { Logout } from '@carbon/icons-react';

import { Abertura } from './abertura/Abertura';
import { Atalhos } from './componentes/Atalhos';
import { PainelDeBastidores } from './bastidores/PainelDeBastidores';
import { SimboloBussola } from './componentes/SimboloBussola';
import { PaginaMapa } from './mapa/PaginaMapa';
import { mensagens } from './mensagens/pt-BR';
import { aoClicarLink, usePagina } from './navegacao';
import { sair, useUsuario } from './sessao';
import { PaginaStatus } from './status/PaginaStatus';

export function App() {
  const pagina = usePagina();
  const usuario = useUsuario();
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
        <HeaderGlobalBar>
          {usuario && <span className="sessao__usuario">{mensagens.sessao.usuario(usuario)}</span>}
          <HeaderGlobalAction
            aria-label={mensagens.sessao.sair}
            tooltipAlignment="end"
            onClick={() => void sair()}
            className="sessao__sair"
          >
            <Logout size={20} />
          </HeaderGlobalAction>
        </HeaderGlobalBar>
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
      <PainelDeBastidores />
      <Atalhos />
      {pagina === 'status' && (
        <Content className="pagina">
          <PaginaStatus />
        </Content>
      )}
    </Theme>
  );
}
