// Ícones do mapa em SVG próprio: o robô do Banco Bússola dentro de um pino, e o pino de chegada.

const url = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

const ROBO = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="120" viewBox="0 0 96 120">
  <path d="M48 116 C48 116 8 70 8 44 A40 40 0 0 1 88 44 C88 70 48 116 48 116 Z" fill="#f26522" stroke="#ffffff" stroke-width="4"/>
  <circle cx="48" cy="44" r="30" fill="#ffffff"/>
  <line x1="48" y1="16" x2="48" y2="24" stroke="#1d3557" stroke-width="3" stroke-linecap="round"/>
  <circle cx="48" cy="14" r="3.5" fill="#f26522"/>
  <rect x="28" y="24" width="40" height="30" rx="9" fill="#1d3557"/>
  <circle cx="39" cy="38" r="5" fill="#7fd1ff"/>
  <circle cx="57" cy="38" r="5" fill="#7fd1ff"/>
  <rect x="38" y="47" width="20" height="3" rx="1.5" fill="#7fd1ff"/>
  <rect x="34" y="56" width="28" height="12" rx="5" fill="#d9dde3"/>
</svg>`;

const CHEGADA = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="120" viewBox="0 0 96 120">
  <path d="M48 116 C48 116 8 70 8 44 A40 40 0 0 1 88 44 C88 70 48 116 48 116 Z" fill="#1d3557" stroke="#ffffff" stroke-width="4"/>
  <path d="M48 20 L68 28 V44 C68 57 59 66 48 70 C37 66 28 57 28 44 V28 Z" fill="#ffffff"/>
  <path d="M38 44 L46 52 L59 36" fill="none" stroke="#f26522" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

// A ponta do pino fica na posição do mapa.
export const ICONE_ROBO = { url: url(ROBO), width: 96, height: 120, anchorY: 120 };
export const ICONE_CHEGADA = { url: url(CHEGADA), width: 96, height: 120, anchorY: 120 };
