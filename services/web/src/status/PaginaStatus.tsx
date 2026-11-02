// Dashboard de status: indicadores, o catálogo em abas e o painel lateral de detalhe.

import { Renew } from '@carbon/icons-react';
import { Button, InlineLoading, InlineNotification, Tab, TabList, TabPanel, TabPanels, Tabs } from '@carbon/react';
import { useCallback, useEffect, useState } from 'react';

import { api, escolherModelo, mudarTool } from '../api';
import { mensagens } from '../mensagens/pt-BR';
import { ABAS, type Rota, useRota } from '../rota';
import type { Catalogo, EstadoDoModelo, Status } from '../tipos';
import { DetalhePrompt, DetalheServico, DetalheSkill, DetalheTool } from './Detalhes';
import { Indicadores } from './Indicadores';
import { PainelLateral } from './Painel';
import { TabelaPrompts, TabelaServicos, TabelaSkills, TabelaTools } from './Tabelas';

const t = mensagens.status;
const INTERVALO_MS = 5000;

export function PaginaStatus() {
  const [rota, ir] = useRota();
  const [status, setStatus] = useState<Status | null>(null);
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null);
  const [modelo, setModelo] = useState<EstadoDoModelo | null>(null);
  const [erroStatus, setErroStatus] = useState(false);
  const [erroCatalogo, setErroCatalogo] = useState(false);
  const [erroAcao, setErroAcao] = useState(false);
  const [erroModelo, setErroModelo] = useState(false);
  const [atualizadoEm, setAtualizadoEm] = useState<Date | null>(null);
  // Resposta imediata no toggle; a próxima consulta ao status confirma o estado real.
  const [otimista, setOtimista] = useState<Record<string, boolean>>({});
  const [pendentes, setPendentes] = useState<Set<string>>(new Set());

  const consultarStatus = useCallback(async () => {
    try {
      setStatus(await api.status());
      setErroStatus(false);
    } catch {
      setErroStatus(true);
    }
    setAtualizadoEm(new Date());
  }, []);

  const consultarCatalogo = useCallback(async () => {
    try {
      setCatalogo(await api.catalogo());
      setErroCatalogo(false);
    } catch {
      setErroCatalogo(true);
    }
  }, []);

  const consultarModelo = useCallback(async () => {
    try {
      setModelo(await api.modelo());
    } catch {
      setModelo(null);
    }
  }, []);

  const atualizar = useCallback(
    () => Promise.all([consultarStatus(), consultarCatalogo(), consultarModelo()]),
    [consultarStatus, consultarCatalogo, consultarModelo],
  );

  async function aoEscolherModelo(id: string) {
    try {
      setModelo(await escolherModelo(id));
      setErroModelo(false);
    } catch {
      setErroModelo(true);
    }
    await consultarStatus();
  }

  useEffect(() => {
    atualizar();
    const id = setInterval(consultarStatus, INTERVALO_MS);
    return () => clearInterval(id);
  }, [atualizar, consultarStatus]);

  // O estado "fora do ar" vem do status (consultado a cada 5 s), não do catálogo.
  const foraNoStatus = new Set(
    (status?.servicos ?? []).flatMap((s) => s.ferramentas.filter((f) => f.fora).map((f) => f.qualificado!)),
  );
  const estaFora = (nome: string) => (nome in otimista ? otimista[nome] : foraNoStatus.has(nome));

  async function executar(acao: () => Promise<void>, nomes: string[]) {
    setPendentes((p) => new Set([...p, ...nomes]));
    try {
      await acao();
      setErroAcao(false);
    } catch {
      setErroAcao(true);
    }
    await consultarStatus();
    setOtimista((o) => Object.fromEntries(Object.entries(o).filter(([n]) => !nomes.includes(n))));
    setPendentes((p) => new Set([...p].filter((n) => !nomes.includes(n))));
  }

  function alternar(nome: string, noAr: boolean) {
    setOtimista((o) => ({ ...o, [nome]: !noAr }));
    executar(() => mudarTool(`${nome}/${noAr ? 'religar' : 'desligar'}`), [nome]);
  }

  function religarTodas() {
    const nomes = (catalogo?.tools ?? []).map((tool) => tool.nome).filter(estaFora);
    setOtimista((o) => ({ ...o, ...Object.fromEntries(nomes.map((n) => [n, false])) }));
    executar(() => mudarTool('religar-todas'), nomes);
  }

  const abrir = (aba: Rota['aba']) => (item: string) => ir({ aba, item });
  const fechar = () => ir({ aba: rota.aba, item: null });

  return (
    <section className={`status${rota.item ? ' status--com-painel' : ''}`} aria-labelledby="titulo-status">
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
          <Button kind="tertiary" size="md" renderIcon={Renew} onClick={atualizar}>
            {t.atualizar}
          </Button>
        </div>
      </div>

      {erroStatus && (
        <InlineNotification
          kind="error"
          lowContrast
          hideCloseButton
          title={t.erroAgente}
          subtitle={t.erroAgenteDetalhe}
        />
      )}
      {erroModelo && (
        <InlineNotification
          kind="error"
          lowContrast
          title={mensagens.indicadores.erroModelo}
          subtitle={mensagens.status.erroAgenteDetalhe}
          onClose={() => setErroModelo(false)}
        />
      )}
      {erroAcao && (
        <InlineNotification
          kind="error"
          lowContrast
          title={mensagens.tools.erroAcao}
          subtitle={mensagens.tools.erroAcaoDetalhe}
          onClose={() => setErroAcao(false)}
        />
      )}

      {!status && !erroStatus && <InlineLoading description={t.carregando} />}
      {status && <Indicadores status={status} modelo={modelo} aoEscolherModelo={aoEscolherModelo} />}

      <Tabs
        selectedIndex={ABAS.indexOf(rota.aba)}
        onChange={({ selectedIndex }: { selectedIndex: number }) => ir({ aba: ABAS[selectedIndex], item: null })}
      >
        <TabList aria-label={mensagens.abas.rotulo} className="status__abas">
          <Tab>{mensagens.abas.servicos}</Tab>
          <Tab>{mensagens.abas.tools}</Tab>
          <Tab>{mensagens.abas.skills}</Tab>
          <Tab>{mensagens.abas.prompts}</Tab>
        </TabList>
        {erroCatalogo && (
          <InlineNotification
            kind="warning"
            lowContrast
            hideCloseButton
            title={t.erroCatalogo}
            subtitle={t.erroCatalogoDetalhe}
          />
        )}
        <TabPanels>
          <TabPanel>
            {status && (
              <TabelaServicos
                servicos={status.servicos}
                selecionado={rota.aba === 'servicos' ? rota.item : null}
                aoAbrir={abrir('servicos')}
              />
            )}
          </TabPanel>
          <TabPanel>
            {catalogo ? (
              <TabelaTools
                catalogo={catalogo}
                estaFora={estaFora}
                pendentes={pendentes}
                alternar={alternar}
                religarTodas={religarTodas}
                selecionado={rota.aba === 'tools' ? rota.item : null}
                aoAbrir={abrir('tools')}
              />
            ) : (
              !erroCatalogo && <InlineLoading description={t.carregando} />
            )}
          </TabPanel>
          <TabPanel>
            {catalogo && (
              <TabelaSkills
                skills={catalogo.skills}
                selecionado={rota.aba === 'skills' ? rota.item : null}
                aoAbrir={abrir('skills')}
              />
            )}
          </TabPanel>
          <TabPanel>
            {catalogo && (
              <TabelaPrompts
                prompts={catalogo.prompts}
                selecionado={rota.aba === 'prompts' ? rota.item : null}
                aoAbrir={abrir('prompts')}
              />
            )}
          </TabPanel>
        </TabPanels>
      </Tabs>

      {rota.item && (
        <Detalhe
          rota={rota}
          status={status}
          catalogo={catalogo}
          estaFora={estaFora}
          pendentes={pendentes}
          alternar={alternar}
          ir={ir}
          fechar={fechar}
        />
      )}
    </section>
  );
}

function Detalhe(props: {
  rota: Rota;
  status: Status | null;
  catalogo: Catalogo | null;
  estaFora: (nome: string) => boolean;
  pendentes: Set<string>;
  alternar: (nome: string, noAr: boolean) => void;
  ir: (rota: Rota) => void;
  fechar: () => void;
}) {
  const { rota, catalogo } = props;
  const item = rota.item!;
  const tipos = mensagens.painel.tipos;
  const naoEncontrado = (tipo: string) => (
    <PainelLateral tipo={tipo} titulo={item} aoFechar={props.fechar}>
      <p className="painel__explicacao">{mensagens.painel.naoEncontrado(item)}</p>
    </PainelLateral>
  );

  if (rota.aba === 'servicos') {
    const servico = props.status?.servicos.find((s) => s.nome === item);
    if (!props.status) return null;
    return servico ? (
      <PainelLateral tipo={tipos.servico} titulo={mensagens.servicos[item] ?? item} aoFechar={props.fechar}>
        <DetalheServico servico={servico} catalogo={catalogo} ir={props.ir} />
      </PainelLateral>
    ) : (
      naoEncontrado(tipos.servico)
    );
  }
  if (!catalogo) return null;
  if (rota.aba === 'tools') {
    const tool = catalogo.tools.find((x) => x.nome === item);
    return tool ? (
      <PainelLateral tipo={tipos.tool} titulo={tool.nome} aoFechar={props.fechar}>
        <DetalheTool
          key={tool.nome}
          tool={tool}
          fora={props.estaFora(tool.nome)}
          pendente={props.pendentes.has(tool.nome)}
          alternar={props.alternar}
          catalogo={catalogo}
          ir={props.ir}
        />
      </PainelLateral>
    ) : (
      naoEncontrado(tipos.tool)
    );
  }
  if (rota.aba === 'skills') {
    const skill = catalogo.skills.find((x) => x.nome === item);
    return skill ? (
      <PainelLateral tipo={tipos.skill} titulo={skill.nome} aoFechar={props.fechar}>
        <DetalheSkill key={skill.nome} skill={skill} catalogo={catalogo} ir={props.ir} />
      </PainelLateral>
    ) : (
      naoEncontrado(tipos.skill)
    );
  }
  const prompt = catalogo.prompts.find((x) => x.nome === item);
  return prompt ? (
    <PainelLateral tipo={tipos.prompt} titulo={prompt.titulo ?? prompt.nome} aoFechar={props.fechar}>
      <DetalhePrompt key={prompt.nome} prompt={prompt} ir={props.ir} />
    </PainelLateral>
  ) : (
    naoEncontrado(tipos.prompt)
  );
}
