// Peças reaproveitadas pelo dashboard: estados, carregamento, código e o histórico do barramento.

import { CheckmarkFilled, ErrorFilled, Renew } from '@carbon/icons-react';
import {
  Button,
  CodeSnippet,
  InlineLoading,
  InlineNotification,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
} from '@carbon/react';
import { type DependencyList, type ReactNode, useCallback, useEffect, useState } from 'react';

import { api } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import type { Chamada, Estado } from '../tipos';

const m = mensagens;

export function TagEstado({ estado }: { estado: Estado }) {
  // Cor nunca sozinha: sempre ícone e rótulo.
  return estado === 'ok' ? (
    <Tag type="green" size="sm" renderIcon={CheckmarkFilled}>
      {m.estado.noAr}
    </Tag>
  ) : (
    <Tag type="red" size="sm" renderIcon={ErrorFilled}>
      {m.estado.foraDoAr}
    </Tag>
  );
}

export function useCarregar<T>(buscar: () => Promise<T>, deps: DependencyList) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState(false);
  const [carregando, setCarregando] = useState(true);
  // As dependências vêm de quem chama, como num useEffect.
  const executar = useCallback(buscar, deps);

  const recarregar = useCallback(async () => {
    setCarregando(true);
    try {
      setDados(await executar());
      setErro(false);
    } catch {
      setErro(true);
    }
    setCarregando(false);
  }, [executar]);

  useEffect(() => {
    setDados(null);
    recarregar();
  }, [recarregar]);

  return { dados, erro, carregando, recarregar };
}

export function Carregavel<T>(props: {
  estado: { dados: T | null; erro: boolean; carregando: boolean };
  children: (dados: T) => ReactNode;
}) {
  const { dados, erro, carregando } = props.estado;
  if (erro) return <InlineNotification kind="error" lowContrast hideCloseButton title={m.painel.erro} />;
  if (dados === null && carregando) return <InlineLoading description={m.painel.carregando} />;
  return dados === null ? null : <>{props.children(dados)}</>;
}

export function Campos(props: { itens: [string, ReactNode][] }) {
  return (
    <dl className="campos">
      {props.itens.map(([rotulo, valor]) => (
        <div key={rotulo} className="campos__linha">
          <dt>{rotulo}</dt>
          <dd>{valor}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Codigo(props: { texto: string; rotulo: string }) {
  return (
    <CodeSnippet
      type="multi"
      wrapText={false}
      maxCollapsedNumberOfRows={60}
      feedback="Copiado"
      copyButtonDescription="Copiar"
      showMoreText="Mostrar mais"
      showLessText="Mostrar menos"
      aria-label={props.rotulo}
      className="codigo"
    >
      {props.texto}
    </CodeSnippet>
  );
}

// Compacto para caber no painel: "01/11 19:32:31".
const hora = (instante: string) => {
  const data = new Date(instante);
  return `${data.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })} ${data.toLocaleTimeString('pt-BR')}`;
};

export function HistoricoDoBarramento(props: {
  filtro: { tool?: string; prompt?: string; skill?: string };
  nomeDaSkill?: (uri: string) => string;
  // Só a skill mistura tipos de evento (carregamentos e chamadas); nos demais, a coluna seria repetida.
  mostrarEvento?: boolean;
}) {
  const t = m.painel.chamadas;
  const chave = JSON.stringify(props.filtro);
  const estado = useCarregar(() => api.chamadas(props.filtro), [chave]);

  return (
    <div className="historico">
      <div className="historico__acoes">
        <Button kind="ghost" size="sm" renderIcon={Renew} onClick={estado.recarregar}>
          {t.atualizar}
        </Button>
      </div>
      <Carregavel estado={estado}>
        {(chamadas: Chamada[]) =>
          chamadas.length === 0 ? (
            <p className="painel__explicacao">{t.vazio}</p>
          ) : (
            <div className="historico__tabela">
              <Table size="sm" useZebraStyles={false}>
                <TableHead>
                  <TableRow>
                    <TableHeader>{t.instante}</TableHeader>
                    {props.mostrarEvento && <TableHeader>{t.evento}</TableHeader>}
                    <TableHeader>{t.status}</TableHeader>
                    <TableHeader>{t.duracao}</TableHeader>
                    <TableHeader>{t.skill}</TableHeader>
                    <TableHeader>{t.execucao}</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {chamadas.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell className="numerico">{hora(c.instante)}</TableCell>
                      {props.mostrarEvento && (
                        <TableCell>{c.tool ? <code>{c.tool}</code> : (t.tipos[c.tipo] ?? c.tipo)}</TableCell>
                      )}
                      <TableCell>
                        {c.status === 'ok' ? (
                          <Tag type="green" size="sm" renderIcon={CheckmarkFilled}>
                            {m.estado.ok}
                          </Tag>
                        ) : (
                          <Tag type="red" size="sm" renderIcon={ErrorFilled} title={c.erro ?? undefined}>
                            {c.motivo ?? m.estado.erro}
                          </Tag>
                        )}
                      </TableCell>
                      <TableCell className="numerico">{c.duracao_ms === null ? '—' : t.ms(c.duracao_ms)}</TableCell>
                      <TableCell className="historico__skill" title={c.skill ?? undefined}>
                        {c.skill ? (
                          (props.nomeDaSkill?.(c.skill) ?? c.skill)
                        ) : (
                          <span className="apagado">{t.semSkill}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {c.execucao_id ? (
                          <code>{c.execucao_id}</code>
                        ) : (
                          <span className="apagado">{t.semExecucao}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )
        }
      </Carregavel>
    </div>
  );
}
