// Símbolo do Banco Bússola: bússola de traço grosso sobre quadrado laranja.
export function SimboloBussola({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="7" fill="#F26522" />
      <circle cx="16" cy="16" r="10" fill="none" stroke="#fff" strokeWidth="3" />
      <path d="M20.5 11.5 L17.6 17.6 L11.5 20.5 L14.4 14.4 Z" fill="#fff" />
    </svg>
  );
}
