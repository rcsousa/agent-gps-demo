// As 8 cenas da demo (spec, "Roteiro da demo, cena a cena"): o preset de cada uma.
// O preset só prepara o palco (mundo, modo, visão); o que acontece depois é sempre real.

export interface Cena {
  numero: string;
  modo: 'com_skill' | 'sem_skill' | 'sem_contexto';
  incidente?: string; // aplicado pelo simulador ao escolher a cena
  raioX?: boolean;
  ultimaViagemComSkill?: boolean; // a cena 8 revê a última viagem com skill no Raio-X
  minutos: number;
  curta: boolean; // faz parte da versão curta (1, 4, 5, 6 e 8)
}

export const CENAS: Cena[] = [
  { numero: '1', modo: 'com_skill', minutos: 1, curta: true },
  { numero: '2', modo: 'sem_contexto', minutos: 1.5, curta: false },
  { numero: '3', modo: 'sem_skill', minutos: 1.5, curta: false },
  { numero: '4', modo: 'com_skill', minutos: 1.5, curta: true },
  { numero: '5', modo: 'com_skill', minutos: 2, curta: true },
  { numero: '6', modo: 'com_skill', incidente: 'cotacao-ancora-fora', minutos: 2, curta: true },
  { numero: '7', modo: 'com_skill', incidente: 'alcada-ana-excedida', minutos: 1, curta: false },
  { numero: '8', modo: 'com_skill', raioX: true, ultimaViagemComSkill: true, minutos: 1.5, curta: true },
];

export const cena = (numero: string | null) => CENAS.find((c) => c.numero === numero);
