// Painéis do Modo Mapa: o nó clicado, as rotas, a legenda e a conversa com a Ana.

import { CheckmarkFilled, ErrorFilled, Send, WarningAltFilled } from '@carbon/icons-react';
import { Button, Link, Tag, TextInput } from '@carbon/react';
import { type ChangeEvent, type MouseEvent, type ReactNode, useEffect, useState } from 'react';

import { api } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import { Campos, Carregavel, useCarregar } from '../status/comum';
import type { EstadoDaViagem } from './viagem';

const t = mensagens.mapa;

export function TagDeStatus({ status }: { status: string | null | undefined }) {
  if (status === 'ok')
    return (
      <Tag type="green" size="sm" renderIcon={CheckmarkFilled}>
        {mensagens.estado.noAr}
      </Tag>
    );
  if (status === 'degradado')
    return (
      <Tag type="warm-gray" size="sm" renderIcon={WarningAltFilled}>
        {t.degradado}
      </Tag>
    );
  if (status === 'fora')
    return (
      <Tag type="red" size="sm" renderIcon={ErrorFilled}>
        {t.interditado}
      </Tag>
    );
  return null;
}

interface Entidade {
  entidade: {
    id: string;
    tipo_exibicao: string;
    nome: string;
    bairro: string;
    descricao?: string;
    atributos: Record<string, unknown>;
    estado: Record<string, unknown> | null;
    proveniencia: Record<string, string> | null;
  };
  relacoes: { tipo: string; sentido: string; entidade: { id: string; nome: string; tipo_exibicao: string } }[];
}

const valor = (v: unknown) => (typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v));

export function DetalheDoNo(props: { id: string; aoEscolher: (id: string) => void }) {
  const estado = useCarregar(() => api.entidade(props.id) as Promise<unknown> as Promise<Entidade>, [props.id]);
  return (
    <Carregavel estado={estado}>
      {({ entidade: e, relacoes }) => (
        <>
          {e.descricao && <p className="painel__descricao">{e.descricao}</p>}
          <Campos
            itens={[
              [t.campos.tipo, e.tipo_exibicao],
              [t.campos.bairro, e.bairro],
              ...(e.estado?.status
                ? ([[t.campos.transito, <TagDeStatus key="s" status={String(e.estado.status)} />]] as [
                    string,
                    ReactNode,
                  ][])
                : []),
              ...(e.estado?.latencia_ms != null
                ? ([[t.campos.latencia, `${e.estado.latencia_ms} ms`]] as [string, string][])
                : []),
              ...Object.entries(e.atributos ?? {}).map(([k, v]): [string, string] => [k, valor(v)]),
            ]}
          />
          {e.proveniencia && (
            <>
              <h3 className="painel__secao">{t.campos.proveniencia}</h3>
              <Campos
                itens={[
                  [t.campos.fonte, e.proveniencia.fonte],
                  [t.campos.data, e.proveniencia.data],
                  [t.campos.responsavel, e.proveniencia.responsavel],
                  [t.campos.confianca, e.proveniencia.confianca],
                ]}
              />
            </>
          )}
          <h3 className="painel__secao">{t.campos.vizinhos(relacoes.length)}</h3>
          <ul className="painel__lista">
            {relacoes.map((r, i) => (
              <li key={`${r.entidade.id}-${i}`}>
                <span className="apagado">{r.tipo.replaceAll('_', ' ').toLowerCase()} </span>
                <Link
                  href="#"
                  onClick={(evento: MouseEvent) => {
                    evento.preventDefault();
                    props.aoEscolher(r.entidade.id);
                  }}
                >
                  {r.entidade.nome}
                </Link>
                <span className="apagado"> · {r.entidade.tipo_exibicao}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Carregavel>
  );
}

export function Legenda() {
  return (
    <details className="mapa__cartao mapa__legenda">
      <summary className="mapa__cartao-titulo">{t.legenda.titulo}</summary>
      <ul>
        <li>
          <span className="mapa__traco mapa__traco--ativa" /> {t.legenda.rastro}
        </li>
        <li>
          <span className="mapa__amostra mapa__amostra--parada">1</span> {t.legenda.parada}
        </li>
        <li>
          <span className="mapa__amostra mapa__amostra--fora">✕</span> {t.legenda.farol}
        </li>
        <li>
          <span className="mapa__amostra mapa__amostra--ok" /> {t.legenda.ok}
        </li>
        <li>
          <span className="mapa__amostra mapa__amostra--degradado">!</span> {t.legenda.degradado}
        </li>
        <li className="mapa__legenda-grupo">{t.legenda.construcoes}</li>
        {t.legenda.estilos.map((e) => (
          <li key={e} className="mapa__legenda-item">
            {e}
          </li>
        ))}
        <li className="apagado">{t.legenda.zoom}</li>
        <li className="apagado">{t.legenda.girar}</li>
      </ul>
    </details>
  );
}

// Responder pela Ana: as opções sugeridas pelo agente e o texto livre.
export function RespostaDaAna(props: {
  pergunta: { texto: string; opcoes: string[] };
  aoResponder: (texto: string) => Promise<void>;
  compacta?: boolean; // no topo do Raio-X: só o necessário para responder
}) {
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  // Respondida: os botões ficam desligados até a próxima pergunta (a resposta ainda vai chegar
  // ao mapa pelo diretor de animações, e não pode haver resposta dupla).
  const [respondida, setRespondida] = useState(false);
  useEffect(() => setRespondida(false), [props.pergunta.texto]);

  async function responder(resposta: string) {
    if (!resposta.trim() || respondida) return;
    setEnviando(true);
    try {
      await props.aoResponder(resposta.trim());
      setTexto('');
      setRespondida(true);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className={`mapa__resposta${props.compacta ? ' mapa__resposta--compacta' : ''}`}>
      <span className="mapa__navegador-rotulo">{t.conversa.respondaPelaAna}</span>
      {props.compacta && <p className="mapa__pergunta">{props.pergunta.texto}</p>}
      <div className="mapa__opcoes">
        {props.pergunta.opcoes.map((opcao) => (
          <Button
            key={opcao}
            kind="tertiary"
            size="sm"
            disabled={enviando || respondida}
            onClick={() => responder(opcao)}
          >
            {opcao}
          </Button>
        ))}
      </div>
      <form
        className="mapa__texto-livre"
        onSubmit={(evento) => {
          evento.preventDefault();
          responder(texto);
        }}
      >
        <TextInput
          id={props.compacta ? 'resposta-livre-raio-x' : 'resposta-livre'}
          size="sm"
          labelText={t.conversa.textoLivre}
          hideLabel
          placeholder={t.conversa.textoLivre}
          value={texto}
          onChange={(e: ChangeEvent<HTMLInputElement>) => setTexto(e.target.value)}
        />
        <Button
          type="submit"
          kind="primary"
          size="sm"
          hasIconOnly
          renderIcon={Send}
          iconDescription={t.conversa.enviar}
          disabled={enviando || respondida || !texto.trim()}
        />
      </form>
    </div>
  );
}

export function Conversa(props: {
  viagem: EstadoDaViagem;
  aoResponder: (texto: string) => Promise<void>;
  embutida?: boolean; // dentro de uma aba do Raio-X: sem moldura própria e sem a resposta (fica no topo)
}) {
  const { viagem } = props;
  return (
    <aside
      className={`mapa__conversa${props.embutida ? ' mapa__conversa--embutida' : ''}`}
      aria-label={t.conversa.titulo}
    >
      {!props.embutida && <h2 className="mapa__cartao-titulo">{t.conversa.titulo}</h2>}
      {viagem.skill && (
        <div className="mapa__navegador">
          <span className="mapa__navegador-rotulo">{t.conversa.navegador}</span>
          <code>{viagem.skill.nome}</code>
        </div>
      )}
      <ol className="mapa__mensagens" aria-live="polite">
        {!viagem.id && <li className="apagado">{t.conversa.vazia}</li>}
        {viagem.mensagens.map((m, i) => (
          <li key={i} className={`mapa__mensagem mapa__mensagem--${m.tipo}`}>
            <span className="mapa__mensagem-autor">{t.conversa.autor[m.tipo]}</span>
            <span className="mapa__mensagem-texto">{m.texto}</span>
          </li>
        ))}
      </ol>
      {viagem.pergunta && !props.embutida && (
        <RespostaDaAna pergunta={viagem.pergunta} aoResponder={props.aoResponder} />
      )}
    </aside>
  );
}
