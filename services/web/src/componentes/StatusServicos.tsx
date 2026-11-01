import { CheckmarkFilled, ErrorFilled, Information, Renew } from '@carbon/icons-react';
import { Button, Column, Grid, InlineLoading, InlineNotification, Tag, Tile } from '@carbon/react';
import { useCallback, useEffect, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';

const t = mensagens.status;
const INTERVALO_MS = 5000;

type Estado = 'ok' | 'fora';

interface Servico {
  nome: string;
  prefixo: string;
  status: Estado;
  latencia_ms: number;
}

interface Status {
  gateway: Estado;
  barramento: Estado;
  llm: { provedor: string; configurado: boolean };
  servicos: Servico[];
  ferramentas: number;
}

function TagEstado({ estado }: { estado: Estado }) {
  // Cor nunca sozinha: sempre ícone e rótulo.
  return estado === 'ok' ? (
    <Tag type="green" renderIcon={CheckmarkFilled}>
      {t.noAr}
    </Tag>
  ) : (
    <Tag type="red" renderIcon={ErrorFilled}>
      {t.foraDoAr}
    </Tag>
  );
}

function TileServico(props: {
  titulo: string;
  tecnico: string;
  estado: Estado;
  latenciaMs?: number;
  detalhe?: string;
}) {
  return (
    <Tile className="tile-servico">
      <span className="tile-servico__nome">{props.titulo}</span>
      <span className="tile-servico__tecnico">{props.tecnico}</span>
      <div className="tile-servico__rodape">
        <TagEstado estado={props.estado} />
        {props.latenciaMs !== undefined && (
          <span className="tile-servico__latencia">{t.latencia(props.latenciaMs)}</span>
        )}
        {props.detalhe && <span className="tile-servico__latencia">{props.detalhe}</span>}
      </div>
    </Tile>
  );
}

export function StatusServicos() {
  const [status, setStatus] = useState<Status | null>(null);
  const [erro, setErro] = useState(false);
  const [atualizadoEm, setAtualizadoEm] = useState<Date | null>(null);

  const consultar = useCallback(async () => {
    try {
      const resposta = await fetch('/api/status');
      if (!resposta.ok) throw new Error(String(resposta.status));
      setStatus(await resposta.json());
      setErro(false);
    } catch {
      setErro(true);
    }
    setAtualizadoEm(new Date());
  }, []);

  useEffect(() => {
    consultar();
    const id = setInterval(consultar, INTERVALO_MS);
    return () => clearInterval(id);
  }, [consultar]);

  const coluna = { sm: 4, md: 4, lg: 4 };

  return (
    <section className="status" aria-labelledby="titulo-status">
      <div className="status__cabecalho">
        <div>
          <h1 id="titulo-status" className="status__titulo">
            {t.titulo}
          </h1>
          <p className="status__descricao">{t.descricao}</p>
        </div>
        <div className="status__acoes">
          {atualizadoEm && (
            <span aria-live="polite">
              {t.ultimaAtualizacao} {atualizadoEm.toLocaleTimeString('pt-BR')}
            </span>
          )}
          <Button kind="tertiary" size="md" renderIcon={Renew} onClick={consultar}>
            {t.atualizar}
          </Button>
        </div>
      </div>

      {erro && (
        <InlineNotification
          kind="error"
          lowContrast
          hideCloseButton
          title={t.erroAgente}
          subtitle={t.erroAgenteDetalhe}
        />
      )}

      {!status && !erro && <InlineLoading description={t.carregando} />}

      {status && (
        <>
          <h2 className="status__grupo">{t.grupos.plataforma}</h2>
          <Grid narrow>
            <Column {...coluna}>
              <TileServico
                titulo={mensagens.servicos.gateway}
                tecnico="mcp-gateway"
                estado={status.gateway}
                detalhe={status.gateway === 'ok' ? t.ferramentas(status.ferramentas) : undefined}
              />
            </Column>
            <Column {...coluna}>
              <TileServico titulo={mensagens.servicos.barramento} tecnico="bus · redis" estado={status.barramento} />
            </Column>
            <Column {...coluna}>
              <Tile className="tile-servico">
                <span className="tile-servico__nome">{t.llm.titulo}</span>
                <span className="tile-servico__tecnico">LLM_PROVIDER={status.llm.provedor}</span>
                <div className="tile-servico__rodape">
                  {status.llm.configurado ? (
                    <Tag type="green" renderIcon={CheckmarkFilled}>
                      {t.llm.provedores[status.llm.provedor]} · {t.llm.configurado}
                    </Tag>
                  ) : (
                    <Tag type="warm-gray" renderIcon={Information}>
                      {t.llm.provedores[status.llm.provedor]} · {t.llm.ausente}
                    </Tag>
                  )}
                </div>
              </Tile>
            </Column>
          </Grid>

          <h2 className="status__grupo">{t.grupos.servidores}</h2>
          <Grid narrow>
            {status.servicos.map((s) => (
              <Column key={s.nome} {...coluna}>
                <TileServico
                  titulo={mensagens.servicos[s.nome] ?? s.nome}
                  tecnico={`${s.nome} · ${s.prefixo}.*`}
                  estado={s.status}
                  latenciaMs={s.latencia_ms}
                />
              </Column>
            ))}
          </Grid>
        </>
      )}
    </section>
  );
}
