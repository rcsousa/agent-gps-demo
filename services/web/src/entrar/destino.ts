// Para onde voltar depois do login. Só caminhos do próprio site: nada de "//outro-site" nem URL
// absoluta (open redirect), e nunca de volta à própria tela de login.
export function destinoSeguro(volta: string | null): string {
  if (!volta || !volta.startsWith('/') || volta.startsWith('//') || volta.startsWith('/\\')) return '/';
  if (volta === '/entrar' || volta.startsWith('/entrar/') || volta.startsWith('/entrar?')) return '/';
  return volta;
}
