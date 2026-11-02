// Medidor de desempenho escondido (/mapa?fps=1): quadros por segundo, tempo de quadro e rótulos.
// Serve para comparar antes e depois de uma otimização e para conferir o notebook do dia.

import { useEffect, useState } from 'react';

import { mensagens } from '../mensagens/pt-BR';

const t = mensagens.mapa.medidor;

export function Medidor(props: { rotulos: number; camadas: number }) {
  const [medida, setMedida] = useState({ fps: 0, quadroMs: 0 });
  useEffect(() => {
    let quadro = 0;
    let inicio = performance.now();
    let quadros = 0;
    let pior = 0;
    let anterior = inicio;
    const passo = (agora: number) => {
      quadros += 1;
      pior = Math.max(pior, agora - anterior);
      anterior = agora;
      if (agora - inicio >= 1000) {
        setMedida({ fps: Math.round((quadros * 1000) / (agora - inicio)), quadroMs: Math.round(pior) });
        inicio = agora;
        quadros = 0;
        pior = 0;
      }
      quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, []);
  return (
    <div className="medidor" data-fps={medida.fps} aria-live="off">
      {t.linha(medida.fps, medida.quadroMs, props.rotulos, props.camadas)}
    </div>
  );
}
