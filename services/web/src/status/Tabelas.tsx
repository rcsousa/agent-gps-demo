// As quatro tabelas do catálogo. Cada linha abre o painel lateral do item.

import { Renew } from '@carbon/icons-react';
import {
  Button,
  Dropdown,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TableToolbar,
  TableToolbarContent,
  TableToolbarSearch,
  Tag,
  Toggle,
} from '@carbon/react';
import { type ReactNode, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';
import type { Catalogo, PromptDoCatalogo, Servico, SkillDoCatalogo, ToolDoCatalogo } from '../tipos';
import { TagEstado } from './comum';

const t = mensagens.tabela;
const c = t.colunas;

interface Coluna<T> {
  titulo: string;
  celula: (item: T) => ReactNode;
  classe?: string;
}

const TODOS = '';

function Tabela<T>(props: {
  id: string;
  itens: T[];
  chave: (item: T) => string;
  texto: (item: T) => string;
  colunas: Coluna<T>[];
  aoAbrir: (chave: string) => void;
  selecionado: string | null;
  servidor?: (item: T) => string;
  descricao?: ReactNode;
  acoes?: ReactNode;
}) {
  const [busca, setBusca] = useState('');
  const [servidor, setServidor] = useState(TODOS);
  const servidores = props.servidor ? [TODOS, ...new Set(props.itens.map(props.servidor))].sort() : [];
  const termo = busca.trim().toLowerCase();
  const visiveis = props.itens.filter(
    (item) =>
      (!termo || props.texto(item).toLowerCase().includes(termo)) && (!servidor || props.servidor?.(item) === servidor),
  );

  return (
    <TableContainer description={props.descricao} className="catalogo__tabela">
      <TableToolbar>
        <TableToolbarContent>
          <TableToolbarSearch
            persistent
            placeholder={t.buscar}
            labelText={t.buscar}
            onChange={(_evento: unknown, valor?: string) => setBusca(valor ?? '')}
          />
          {props.servidor && (
            <Dropdown
              id={`${props.id}-servidor`}
              className="catalogo__filtro"
              type="inline"
              titleText={t.filtrarServidor}
              hideLabel
              label={t.todosOsServidores}
              items={servidores}
              itemToString={(s: string | null) => (s ? s : t.todosOsServidores)}
              selectedItem={servidor}
              onChange={({ selectedItem }: { selectedItem: string | null }) => setServidor(selectedItem ?? TODOS)}
            />
          )}
          {props.acoes}
        </TableToolbarContent>
      </TableToolbar>
      <Table size="md">
        <TableHead>
          <TableRow>
            {props.colunas.map((coluna) => (
              <TableHeader key={coluna.titulo} className={coluna.classe}>
                {coluna.titulo}
              </TableHeader>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {visiveis.map((item) => {
            const chave = props.chave(item);
            return (
              <TableRow
                key={chave}
                className="catalogo__linha"
                isSelected={chave === props.selecionado}
                onClick={() => props.aoAbrir(chave)}
              >
                {props.colunas.map((coluna) => (
                  <TableCell key={coluna.titulo} className={coluna.classe}>
                    {coluna.celula(item)}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
          {visiveis.length === 0 && (
            <TableRow>
              <TableCell colSpan={props.colunas.length} className="apagado">
                {t.nenhum}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

// O nome é um botão de verdade: a linha inteira é clicável, mas o teclado também chega lá.
function Abrir(props: { nome: string; aoAbrir: () => void; children?: ReactNode }) {
  return (
    <button
      type="button"
      className="catalogo__abrir"
      aria-label={t.abrir(props.nome)}
      onClick={(evento) => {
        evento.stopPropagation();
        props.aoAbrir();
      }}
    >
      {props.children ?? props.nome}
    </button>
  );
}

export function TabelaServicos(props: {
  servicos: Servico[];
  selecionado: string | null;
  aoAbrir: (nome: string) => void;
}) {
  return (
    <Tabela
      id="servicos"
      itens={props.servicos}
      chave={(s) => s.nome}
      texto={(s) => `${s.nome} ${mensagens.servicos[s.nome] ?? ''} ${s.prefixo}`}
      selecionado={props.selecionado}
      aoAbrir={props.aoAbrir}
      colunas={[
        {
          titulo: c.servidor,
          celula: (s) => (
            <Abrir nome={s.nome} aoAbrir={() => props.aoAbrir(s.nome)}>
              <strong>{mensagens.servicos[s.nome] ?? s.nome}</strong> <code>{s.nome}</code>
            </Abrir>
          ),
        },
        { titulo: c.prefixo, celula: (s) => <code>{s.prefixo}.*</code> },
        { titulo: c.status, celula: (s) => <TagEstado estado={s.status} /> },
        { titulo: c.latencia, celula: (s) => mensagens.status.latencia(s.latencia_ms), classe: 'numerico' },
        { titulo: c.tools, celula: (s) => s.ferramentas.filter((f) => f.visivel).length, classe: 'numerico' },
        { titulo: c.prompts, celula: (s) => s.prompts.length, classe: 'numerico' },
        { titulo: c.skills, celula: (s) => s.skills.length, classe: 'numerico' },
      ]}
    />
  );
}

export function TabelaTools(props: {
  catalogo: Catalogo;
  estaFora: (nome: string) => boolean;
  pendentes: Set<string>;
  alternar: (nome: string, noAr: boolean) => void;
  religarTodas: () => void;
  selecionado: string | null;
  aoAbrir: (nome: string) => void;
}) {
  const tt = mensagens.tools;
  const fora = props.catalogo.tools.filter((tool) => props.estaFora(tool.nome)).length;
  return (
    <Tabela<ToolDoCatalogo>
      id="tools"
      itens={props.catalogo.tools}
      chave={(tool) => tool.nome}
      texto={(tool) => `${tool.nome} ${tool.descricao} ${tool.servidor}`}
      servidor={(tool) => tool.servidor}
      selecionado={props.selecionado}
      aoAbrir={props.aoAbrir}
      descricao={tt.descricao}
      acoes={
        <>
          <span className="catalogo__contagem" aria-live="polite">
            {tt.contagemFora(fora)}
          </span>
          <Button kind="primary" size="md" renderIcon={Renew} disabled={fora === 0} onClick={props.religarTodas}>
            {tt.religarTodas}
          </Button>
        </>
      }
      colunas={[
        {
          titulo: c.tool,
          celula: (tool) => (
            <Abrir nome={tool.nome} aoAbrir={() => props.aoAbrir(tool.nome)}>
              <code>{tool.nome}</code>
            </Abrir>
          ),
        },
        { titulo: c.servidor, celula: (tool) => <code className="apagado">{tool.servidor}</code> },
        { titulo: c.descricao, celula: (tool) => <span className="catalogo__descricao">{tool.descricao}</span> },
        {
          titulo: c.usadaPor,
          celula: (tool) =>
            tool.skills.length ? (
              <Tag type="blue" size="sm">
                {tt.skills(tool.skills.length)}
              </Tag>
            ) : (
              <span className="apagado">{tt.nenhumaSkill}</span>
            ),
        },
        { titulo: c.status, celula: (tool) => <TagEstado estado={props.estaFora(tool.nome) ? 'fora' : 'ok'} /> },
        {
          titulo: c.ligada,
          classe: 'catalogo__controle',
          celula: (tool) => (
            <div onClick={(evento) => evento.stopPropagation()}>
              <Toggle
                id={`tool-${tool.nome}`}
                size="sm"
                labelText={tt.rotuloToggle(tool.nome)}
                hideLabel
                labelA={mensagens.estado.foraDoAr}
                labelB={mensagens.estado.noAr}
                toggled={!props.estaFora(tool.nome)}
                disabled={props.pendentes.has(tool.nome)}
                onToggle={(noAr: boolean) => props.alternar(tool.nome, noAr)}
              />
            </div>
          ),
        },
      ]}
    />
  );
}

export function TabelaSkills(props: {
  skills: SkillDoCatalogo[];
  selecionado: string | null;
  aoAbrir: (nome: string) => void;
}) {
  return (
    <Tabela<SkillDoCatalogo>
      id="skills"
      itens={props.skills}
      chave={(s) => s.nome}
      texto={(s) => `${s.nome} ${s.descricao}`}
      selecionado={props.selecionado}
      aoAbrir={props.aoAbrir}
      colunas={[
        {
          titulo: c.skill,
          celula: (s) => (
            <Abrir nome={s.nome} aoAbrir={() => props.aoAbrir(s.nome)}>
              <code>{s.nome}</code>
            </Abrir>
          ),
        },
        { titulo: c.descricao, celula: (s) => <span className="catalogo__descricao">{s.descricao}</span> },
        { titulo: c.toolsPermitidas, celula: (s) => s.tools.length, classe: 'numerico' },
        {
          titulo: c.reutiliza,
          celula: (s) =>
            s.usa_skills.length ? (
              <span className="catalogo__tags">
                {s.usa_skills.map((nome) => (
                  <Tag key={nome} type="cool-gray" size="sm">
                    {nome}
                  </Tag>
                ))}
              </span>
            ) : (
              <span className="apagado">—</span>
            ),
        },
        { titulo: c.arquivos, celula: (s) => s.arquivos.length, classe: 'numerico' },
        { titulo: c.servidor, celula: (s) => <code className="apagado">{s.servidor}</code> },
      ]}
    />
  );
}

export function TabelaPrompts(props: {
  prompts: PromptDoCatalogo[];
  selecionado: string | null;
  aoAbrir: (nome: string) => void;
}) {
  return (
    <Tabela<PromptDoCatalogo>
      id="prompts"
      itens={props.prompts}
      chave={(p) => p.nome}
      texto={(p) => `${p.nome} ${p.titulo ?? ''} ${p.descricao} ${p.interlocutor ?? ''}`}
      selecionado={props.selecionado}
      aoAbrir={props.aoAbrir}
      colunas={[
        {
          titulo: c.prompt,
          celula: (p) => (
            <Abrir nome={p.nome} aoAbrir={() => props.aoAbrir(p.nome)}>
              <strong>{p.titulo ?? p.nome}</strong> <code>{p.nome}</code>
            </Abrir>
          ),
        },
        { titulo: c.canal, celula: (p) => <code>{p.canal ?? '—'}</code> },
        { titulo: c.interlocutor, celula: (p) => p.interlocutor ?? '—' },
        { titulo: c.argumentos, celula: (p) => p.argumentos.map((a) => a.nome).join(', ') || '—' },
        { titulo: c.servidor, celula: (p) => <code className="apagado">{p.servidor}</code> },
      ]}
    />
  );
}
