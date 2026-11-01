// O que cada item é por dentro: contrato, uso e código (tool), workflow (skill) e persona (prompt).

import { CheckmarkFilled } from '@carbon/icons-react';
import {
  Link,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tag,
  Toggle,
} from '@carbon/react';
import { type MouseEvent, type ReactNode, useState } from 'react';
import ReactMarkdown from 'react-markdown';

import { api, uriDeFonte } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import type { Rota } from '../rota';
import type {
  Catalogo,
  EsquemaJson,
  Fonte,
  PromptDoCatalogo,
  Servico,
  SkillDoCatalogo,
  ToolDoCatalogo,
} from '../tipos';
import { Campos, Carregavel, Codigo, HistoricoDoBarramento, TagEstado, useCarregar } from './comum';

const t = mensagens.painel;
type Ir = (rota: Rota) => void;

// Link de verdade (abre em outra aba, copia a URL) que navega sem recarregar a página.
function LinkInterno(props: { rota: Rota; ir: Ir; children: ReactNode }) {
  const href = `/status/${props.rota.aba}/${encodeURIComponent(props.rota.item ?? '')}`;
  return (
    <Link
      href={href}
      onClick={(evento: MouseEvent) => {
        evento.preventDefault();
        props.ir(props.rota);
      }}
    >
      {props.children}
    </Link>
  );
}

function Abas(props: { rotulo: string; abas: [string, ReactNode][] }) {
  return (
    <Tabs>
      <TabList aria-label={props.rotulo} contained fullWidth>
        {props.abas.map(([nome]) => (
          <Tab key={nome}>{nome}</Tab>
        ))}
      </TabList>
      <TabPanels>
        {props.abas.map(([nome, conteudo]) => (
          <TabPanel key={nome} className="painel__aba">
            {conteudo}
          </TabPanel>
        ))}
      </TabPanels>
    </Tabs>
  );
}

function Markdown({ texto }: { texto: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown>{texto}</ReactMarkdown>
    </div>
  );
}

const semFrontmatter = (texto: string) =>
  texto.startsWith('---\n') ? texto.slice(texto.indexOf('\n---\n', 4) + 5) : texto;

function CodigoFonte(props: { uri: string; rotulo: string }) {
  const estado = useCarregar(() => api.fonte(props.uri), [props.uri]);
  return (
    <Carregavel estado={estado}>
      {(fonte: Fonte) => (
        <>
          <p className="painel__origem">
            <code>{t.codigo.origem(fonte.arquivo, fonte.linha)}</code>
          </p>
          <Codigo texto={fonte.texto} rotulo={props.rotulo} />
          <p className="painel__explicacao">{t.codigo.explicacao}</p>
        </>
      )}
    </Carregavel>
  );
}

// --- Tool -----------------------------------------------------------------------------

function tipoDe(esquema: EsquemaJson): string {
  if (esquema.anyOf) return esquema.anyOf.map(tipoDe).join(' | ');
  if (esquema.type === 'array') return `${tipoDe(esquema.items ?? {})}[]`;
  if (esquema.enum) return esquema.enum.map((v) => JSON.stringify(v)).join(' | ');
  return esquema.type ?? 'objeto';
}

function Contrato({ tool }: { tool: ToolDoCatalogo }) {
  const c = t.contrato;
  const parametros = Object.entries(tool.esquema_entrada.properties ?? {});
  const obrigatorios = new Set(tool.esquema_entrada.required ?? []);
  return (
    <>
      <h3 className="painel__secao">{c.entrada}</h3>
      {parametros.length === 0 ? (
        <p className="painel__explicacao">{c.semParametros}</p>
      ) : (
        <Table size="sm">
          <TableHead>
            <TableRow>
              <TableHeader>{c.parametro}</TableHeader>
              <TableHeader>{c.tipo}</TableHeader>
              <TableHeader>{c.obrigatorio}</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {parametros.map(([nome, esquema]) => (
              <TableRow key={nome}>
                <TableCell>
                  <code>{nome}</code>
                  {esquema.description && <div className="apagado">{esquema.description}</div>}
                </TableCell>
                <TableCell>
                  <code>{tipoDe(esquema)}</code>
                </TableCell>
                <TableCell>{obrigatorios.has(nome) ? c.sim : c.nao}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Codigo texto={JSON.stringify(tool.esquema_entrada, null, 2)} rotulo={`${c.esquema} · ${c.entrada}`} />
      <h3 className="painel__secao">{c.saida}</h3>
      {tool.esquema_saida ? (
        <Codigo texto={JSON.stringify(tool.esquema_saida, null, 2)} rotulo={`${c.esquema} · ${c.saida}`} />
      ) : (
        <p className="painel__explicacao">{c.semSaida}</p>
      )}
    </>
  );
}

export function DetalheTool(props: {
  tool: ToolDoCatalogo;
  fora: boolean;
  pendente: boolean;
  alternar: (nome: string, noAr: boolean) => void;
  catalogo: Catalogo;
  ir: Ir;
}) {
  const { tool } = props;
  const f = t.campos;
  const anotacoes = Object.entries(tool.anotacoes);
  return (
    <Abas
      rotulo={tool.nome}
      abas={[
        [
          t.abas.visaoGeral,
          <>
            <p className="painel__descricao">{tool.descricao}</p>
            <Campos
              itens={[
                [
                  f.servidor,
                  <LinkInterno key="s" rota={{ aba: 'servicos', item: tool.servidor }} ir={props.ir}>
                    <code>{tool.servidor}</code>
                  </LinkInterno>,
                ],
                [f.nomeOriginal, <code key="n">{tool.nome_original}</code>],
                [f.status, <TagEstado key="e" estado={props.fora ? 'fora' : 'ok'} />],
                [
                  f.ligada,
                  <div key="t" className="catalogo__controle">
                    <Toggle
                      id={`painel-${tool.nome}`}
                      size="sm"
                      labelText={mensagens.tools.rotuloToggle(tool.nome)}
                      hideLabel
                      labelA={mensagens.estado.foraDoAr}
                      labelB={mensagens.estado.noAr}
                      toggled={!props.fora}
                      disabled={props.pendente}
                      onToggle={(noAr: boolean) => props.alternar(tool.nome, noAr)}
                    />
                  </div>,
                ],
                [
                  f.anotacoes,
                  anotacoes.length ? (
                    <span className="catalogo__tags">
                      {anotacoes.map(([chave, valor]) => (
                        <Tag key={chave} type="cool-gray" size="sm">
                          {chave}: {String(valor)}
                        </Tag>
                      ))}
                    </span>
                  ) : (
                    f.semAnotacoes
                  ),
                ],
              ]}
            />
            <h3 className="painel__secao">{f.permitidaPor}</h3>
            {tool.skills.length === 0 ? (
              <p className="painel__explicacao">{f.nenhumaSkill}</p>
            ) : (
              <ul className="painel__lista">
                {tool.skills.map((s) => (
                  <li key={s.uri}>
                    <LinkInterno rota={{ aba: 'skills', item: s.nome }} ir={props.ir}>
                      {s.nome}
                    </LinkInterno>
                    {!s.direta && <span className="apagado"> · {f.viaReuso}</span>}
                  </li>
                ))}
              </ul>
            )}
          </>,
        ],
        [t.abas.contrato, <Contrato key="c" tool={tool} />],
        [
          t.abas.codigo,
          <CodigoFonte key="f" uri={uriDeFonte(tool.servidor, 'tool', tool.nome_original)} rotulo={tool.nome} />,
        ],
        [
          t.abas.chamadas,
          <HistoricoDoBarramento key="h" filtro={{ tool: tool.nome }} nomeDaSkill={nomeDaSkill(props.catalogo)} />,
        ],
      ]}
    />
  );
}

const nomeDaSkill = (catalogo: Catalogo) => (uri: string) => catalogo.skills.find((s) => s.uri === uri)?.nome ?? uri;

// --- Skill ----------------------------------------------------------------------------

function ArquivoDeSkill({ uri }: { uri: string }) {
  const estado = useCarregar(() => api.arquivoDeSkill(uri), [uri]);
  return (
    <Carregavel estado={estado}>
      {(arquivo) => (
        <>
          <p className="painel__origem">
            <Tag type="green" size="sm" renderIcon={CheckmarkFilled}>
              {t.arquivos.verificado}
            </Tag>{' '}
            <code>{arquivo.digest.slice(0, 23)}…</code> · {t.arquivos.bytes(arquivo.size)}
          </p>
          <Markdown texto={semFrontmatter(arquivo.texto)} />
        </>
      )}
    </Carregavel>
  );
}

function ArquivosDaSkill({ skill }: { skill: SkillDoCatalogo }) {
  const apoio = skill.arquivos.filter((a) => a.uri !== skill.uri);
  const [aberto, setAberto] = useState(apoio[0]?.uri ?? null);
  return (
    <>
      <ul className="painel__arquivos">
        {apoio.map((a) => (
          <li key={a.uri}>
            <button
              type="button"
              className={`painel__arquivo${a.uri === aberto ? ' painel__arquivo--aberto' : ''}`}
              aria-pressed={a.uri === aberto}
              onClick={() => setAberto(a.uri)}
            >
              <code>{a.uri.split('/').slice(3).join('/')}</code>
              <span className="apagado">{t.arquivos.bytes(a.size)}</span>
            </button>
          </li>
        ))}
      </ul>
      {aberto && <ArquivoDeSkill uri={aberto} />}
    </>
  );
}

export function DetalheSkill(props: { skill: SkillDoCatalogo; catalogo: Catalogo; ir: Ir }) {
  const { skill } = props;
  const f = t.campos;
  const metadados = Object.entries(skill.frontmatter.metadata ?? {}).filter(([chave]) => chave !== 'usa-skills');
  return (
    <Abas
      rotulo={skill.nome}
      abas={[
        [
          t.abas.visaoGeral,
          <>
            <p className="painel__descricao">{skill.descricao}</p>
            <Campos
              itens={[
                [f.uri, <code key="u">{skill.uri}</code>],
                [
                  f.servidor,
                  <LinkInterno key="s" rota={{ aba: 'servicos', item: skill.servidor }} ir={props.ir}>
                    <code>{skill.servidor}</code>
                  </LinkInterno>,
                ],
                [
                  f.reutiliza,
                  skill.usa_skills.length ? (
                    <span className="catalogo__tags">
                      {skill.usa_skills.map((nome) => (
                        <LinkInterno key={nome} rota={{ aba: 'skills', item: nome }} ir={props.ir}>
                          {nome}
                        </LinkInterno>
                      ))}
                    </span>
                  ) : (
                    f.nenhuma
                  ),
                ],
                ...metadados.map(([chave, valor]): [string, ReactNode] => [chave, String(valor)]),
              ]}
            />
            <h3 className="painel__secao">{f.tools}</h3>
            <ul className="painel__lista painel__lista--colunas">
              {skill.tools.map((nome) => (
                <li key={nome}>
                  <LinkInterno rota={{ aba: 'tools', item: nome }} ir={props.ir}>
                    <code>{nome}</code>
                  </LinkInterno>
                </li>
              ))}
            </ul>
            {skill.tools_com_reuso.length > skill.tools.length && (
              <p className="painel__explicacao">{f.toolsComReuso(skill.tools_com_reuso.length)}</p>
            )}
          </>,
        ],
        [t.abas.skillMd, <ArquivoDeSkill key="md" uri={skill.uri} />],
        [t.abas.arquivos, <ArquivosDaSkill key="a" skill={skill} />],
        [
          t.abas.uso,
          <HistoricoDoBarramento
            key="h"
            filtro={{ skill: skill.uri }}
            nomeDaSkill={nomeDaSkill(props.catalogo)}
            mostrarEvento
          />,
        ],
      ]}
    />
  );
}

// --- Prompt ---------------------------------------------------------------------------

function Previa({ nome }: { nome: string }) {
  const estado = useCarregar(() => api.previa(nome), [nome]);
  return (
    <Carregavel estado={estado}>
      {(previa) => (
        <>
          <p className="painel__explicacao">{t.previa.explicacao(previa.cliente_id)}</p>
          <div className="painel__previa">
            <Markdown texto={previa.texto} />
          </div>
        </>
      )}
    </Carregavel>
  );
}

export function DetalhePrompt(props: { prompt: PromptDoCatalogo; ir: Ir }) {
  const { prompt } = props;
  const f = t.campos;
  const nomeNoServidor = prompt.nome.split('.').slice(1).join('.');
  return (
    <Abas
      rotulo={prompt.nome}
      abas={[
        [
          t.abas.visaoGeral,
          <>
            <p className="painel__descricao">{prompt.descricao}</p>
            <Campos
              itens={[
                [f.canal, <code key="c">{prompt.canal ?? '—'}</code>],
                [f.interlocutor, prompt.interlocutor ?? '—'],
                [
                  f.servidor,
                  <LinkInterno key="s" rota={{ aba: 'servicos', item: prompt.servidor }} ir={props.ir}>
                    <code>{prompt.servidor}</code>
                  </LinkInterno>,
                ],
                [f.nomeOriginal, <code key="n">{nomeNoServidor}</code>],
                [
                  f.argumentos,
                  <ul key="a" className="painel__lista">
                    {prompt.argumentos.map((a) => (
                      <li key={a.nome}>
                        <code>{a.nome}</code> · {a.obrigatorio ? f.obrigatorio : f.opcional}
                      </li>
                    ))}
                  </ul>,
                ],
              ]}
            />
          </>,
        ],
        [t.abas.previa, <Previa key="p" nome={prompt.nome} />],
        [
          t.abas.fonte,
          <CodigoFonte key="f" uri={uriDeFonte(prompt.servidor, 'prompt', nomeNoServidor)} rotulo={prompt.nome} />,
        ],
        [t.abas.leituras, <HistoricoDoBarramento key="h" filtro={{ prompt: prompt.nome }} />],
      ]}
    />
  );
}

// --- Servidor MCP ---------------------------------------------------------------------

export function DetalheServico(props: { servico: Servico; catalogo: Catalogo | null; ir: Ir }) {
  const { servico } = props;
  const f = t.campos;
  const nomeDaSkillUri = (uri: string) => props.catalogo?.skills.find((s) => s.uri === uri)?.nome ?? uri;
  return (
    <Abas
      rotulo={servico.nome}
      abas={[
        [
          t.abas.visaoGeral,
          <Campos
            key="v"
            itens={[
              [f.status, <TagEstado key="e" estado={servico.status} />],
              [f.prefixo, <code key="p">{servico.prefixo}.*</code>],
              [f.latencia, mensagens.status.latencia(servico.latencia_ms)],
            ]}
          />,
        ],
        [
          t.abas.oferece,
          <>
            <h3 className="painel__secao">{mensagens.abas.tools}</h3>
            <ul className="painel__lista">
              {servico.ferramentas.map((ferramenta) => (
                <li key={ferramenta.nome}>
                  {ferramenta.qualificado ? (
                    <LinkInterno rota={{ aba: 'tools', item: ferramenta.qualificado }} ir={props.ir}>
                      <code>{ferramenta.qualificado}</code>
                    </LinkInterno>
                  ) : (
                    <>
                      <code>{ferramenta.nome}</code> <span className="apagado">· {f.oculta}</span>
                    </>
                  )}
                </li>
              ))}
            </ul>
            {servico.prompts.length > 0 && (
              <>
                <h3 className="painel__secao">{mensagens.abas.prompts}</h3>
                <ul className="painel__lista">
                  {servico.prompts.map((nome) => (
                    <li key={nome}>
                      <LinkInterno rota={{ aba: 'prompts', item: nome }} ir={props.ir}>
                        <code>{nome}</code>
                      </LinkInterno>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {servico.skills.length > 0 && (
              <>
                <h3 className="painel__secao">{mensagens.abas.skills}</h3>
                <ul className="painel__lista">
                  {servico.skills.map((uri) => (
                    <li key={uri}>
                      <LinkInterno rota={{ aba: 'skills', item: nomeDaSkillUri(uri) }} ir={props.ir}>
                        <code>{nomeDaSkillUri(uri)}</code>
                      </LinkInterno>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>,
        ],
      ]}
    />
  );
}
