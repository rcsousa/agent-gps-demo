import { Button, Form, InlineNotification, PasswordInput, Stack, TextInput, Theme } from '@carbon/react';
import { ArrowRight } from '@carbon/icons-react';
import { type FormEvent, useEffect, useState } from 'react';

import { SimboloBussola } from '../componentes/SimboloBussola';
import { mensagensDoLogin as t } from '../mensagens/pt-BR';
import { destinoSeguro } from './destino';

type Erro = { tipo: 'credenciais' } | { tipo: 'muitasTentativas'; minutos: number } | { tipo: 'semUsuarios' } | { tipo: 'falha' } | { tipo: 'obrigatorio' };

function textoDoErro(erro: Erro): string {
  switch (erro.tipo) {
    case 'credenciais':
      return t.erros.credenciais;
    case 'muitasTentativas':
      return t.erros.muitasTentativas(erro.minutos);
    case 'semUsuarios':
      return t.erros.semUsuarios;
    case 'obrigatorio':
      return t.obrigatorio;
    default:
      return t.erros.falha;
  }
}

export function PaginaEntrar() {
  const destino = destinoSeguro(new URLSearchParams(window.location.search).get('volta'));
  const [usuario, setUsuario] = useState('');
  const [senha, setSenha] = useState('');
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<Erro | null>(null);

  // Quem já tem sessão nem vê o formulário.
  useEffect(() => {
    fetch('/auth/eu', { cache: 'no-store' })
      .then((resposta) => {
        if (resposta.ok) window.location.replace(destino);
      })
      .catch(() => undefined);
  }, [destino]);

  async function entrar(evento: FormEvent) {
    evento.preventDefault();
    if (!usuario.trim() || !senha) {
      setErro({ tipo: 'obrigatorio' });
      return;
    }
    setEnviando(true);
    setErro(null);
    try {
      const resposta = await fetch('/auth/entrar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario: usuario.trim(), senha }),
      });
      if (resposta.ok) {
        window.location.replace(destino);
        return;
      }
      const corpo = await resposta.json().catch(() => ({}));
      if (resposta.status === 429) {
        setErro({ tipo: 'muitasTentativas', minutos: Math.max(1, Math.ceil((corpo.espera_s ?? 60) / 60)) });
      } else if (resposta.status === 503 && corpo.erro === 'sem_usuarios') {
        setErro({ tipo: 'semUsuarios' });
      } else if (resposta.status === 401) {
        setErro({ tipo: 'credenciais' });
      } else {
        setErro({ tipo: 'falha' });
      }
      setSenha('');
    } catch {
      setErro({ tipo: 'falha' });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Theme theme="g100" className="entrar">
      <main className="entrar__cartao" aria-labelledby="entrar-titulo">
        <div className="entrar__marca">
          <SimboloBussola className="entrar__simbolo" />
          <span>
            {t.marca.prefixo} <strong className="entrar__nome">{t.marca.nome}</strong>
          </span>
        </div>
        <h1 id="entrar-titulo" className="entrar__titulo">
          {t.titulo}
        </h1>
        <p className="entrar__subtitulo">{t.subtitulo}</p>
        <Form onSubmit={entrar} noValidate aria-describedby={erro ? 'entrar-erro' : undefined}>
          <Stack gap={6}>
            {erro && (
              <InlineNotification
                id="entrar-erro"
                kind="error"
                role="alert"
                lowContrast
                hideCloseButton
                title={t.erroTitulo}
                subtitle={textoDoErro(erro)}
              />
            )}
            <TextInput
              id="entrar-usuario"
              labelText={t.usuario}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              disabled={enviando}
              autoFocus
            />
            <PasswordInput
              id="entrar-senha"
              labelText={t.senha}
              autoComplete="current-password"
              showPasswordLabel={t.mostrarSenha}
              hidePasswordLabel={t.esconderSenha}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              disabled={enviando}
            />
            <Button type="submit" renderIcon={ArrowRight} disabled={enviando} className="entrar__botao">
              {enviando ? t.entrando : t.entrar}
            </Button>
          </Stack>
        </Form>
        <p className="entrar__assinatura">{t.marca.assinatura}</p>
      </main>
      <p className="entrar__rodape">{t.rodape}</p>
    </Theme>
  );
}
