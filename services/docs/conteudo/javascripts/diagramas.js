// Diagramas com zoom: cada imagem de assets/diagramas/*.svg vira um visualizador com o SVG embutido
// (assim ele usa as fontes IBM Plex do site), com zoom, arrasto, enquadrar, tela cheia e o link para
// o arquivo. O zoom pela roda do mouse só vale com o diagrama ativo (um clique nele), para não
// sequestrar a rolagem da página. Teclado: + e − aproximam e afastam, 0 enquadra.
(function () {
  "use strict";

  var ZOOM_MAXIMO = 40;

  function botao(rotulo, texto, aoClicar) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "diagrama__botao";
    b.setAttribute("aria-label", rotulo);
    b.title = rotulo;
    b.textContent = texto;
    b.addEventListener("click", aoClicar);
    return b;
  }

  function montar(imagem) {
    var endereco = imagem.getAttribute("src");
    var descricao = imagem.getAttribute("alt") || "Diagrama";

    var figura = document.createElement("figure");
    figura.className = "diagrama";
    var palco = document.createElement("div");
    palco.className = "diagrama__palco";
    palco.tabIndex = 0;
    palco.setAttribute("role", "group");
    palco.setAttribute("aria-label", descricao + ". Clique para ativar o zoom pela roda do mouse; + e − aproximam, 0 enquadra.");
    var barra = document.createElement("div");
    barra.className = "diagrama__barra";
    var legenda = document.createElement("figcaption");
    legenda.className = "diagrama__legenda";
    legenda.textContent = descricao;

    imagem.replaceWith(figura);
    figura.appendChild(barra);
    figura.appendChild(palco);
    figura.appendChild(legenda);
    palco.appendChild(imagem); // enquanto o SVG não chega, a imagem continua visível

    fetch(endereco)
      .then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.text();
      })
      .then(function (texto) {
        var svg = new DOMParser().parseFromString(texto, "image/svg+xml").documentElement;
        if (svg.nodeName.toLowerCase() !== "svg") throw new Error("não é SVG");
        svg.removeAttribute("width");
        svg.removeAttribute("height");
        svg.setAttribute("role", "img");
        svg.setAttribute("aria-label", descricao);
        svg.classList.add("diagrama__svg");
        palco.replaceChild(document.importNode(svg, true), imagem);
        var alvo = palco.querySelector("svg");
        // A altura acompanha a proporção do diagrama (um largo e baixo não fica perdido num palco
        // alto), com teto de 70% da janela: o resto se vê com zoom ou em tela cheia.
        var caixa = alvo.viewBox && alvo.viewBox.baseVal;
        var largura = palco.clientWidth || 800;
        var natural = caixa && caixa.width ? (largura * caixa.height) / caixa.width : 400;
        palco.style.blockSize = Math.round(Math.max(160, Math.min(natural + 16, window.innerHeight * 0.7))) + "px";

        var zoom = window.svgPanZoom(alvo, {
          zoomEnabled: true,
          mouseWheelZoomEnabled: false,
          dblClickZoomEnabled: true,
          controlIconsEnabled: false,
          fit: true,
          center: true,
          minZoom: 0.2,
          maxZoom: ZOOM_MAXIMO,
          zoomScaleSensitivity: 0.3,
        });
        figura.dataset.zoom = "pronto";
        var registrar = function () {
          figura.dataset.escala = zoom.getZoom().toFixed(2);
        };
        zoom.setOnZoom(registrar);
        registrar();

        var enquadrar = function () {
          zoom.resize();
          zoom.fit();
          zoom.center();
        };
        barra.appendChild(botao("Aproximar", "+", function () { zoom.zoomIn(); }));
        barra.appendChild(botao("Afastar", "−", function () { zoom.zoomOut(); }));
        barra.appendChild(botao("Enquadrar o diagrama", "⤢", enquadrar));
        barra.appendChild(
          botao("Tela cheia", "⛶", function () {
            if (document.fullscreenElement) document.exitFullscreen();
            else if (figura.requestFullscreen) figura.requestFullscreen();
          })
        );
        var link = document.createElement("a");
        link.className = "diagrama__abrir";
        link.href = endereco;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = "Abrir o SVG";
        barra.appendChild(link);

        // A roda do mouse só dá zoom com o diagrama ativo (clicado); sair dele devolve a rolagem.
        palco.addEventListener("click", function () {
          zoom.enableMouseWheelZoom();
          figura.classList.add("diagrama--ativo");
        });
        figura.addEventListener("mouseleave", function () {
          if (document.fullscreenElement === figura) return;
          zoom.disableMouseWheelZoom();
          figura.classList.remove("diagrama--ativo");
        });
        palco.addEventListener("keydown", function (e) {
          if (e.key === "+" || e.key === "=") zoom.zoomIn();
          else if (e.key === "-" || e.key === "_") zoom.zoomOut();
          else if (e.key === "0") enquadrar();
          else return;
          e.preventDefault();
        });
        document.addEventListener("fullscreenchange", function () {
          var cheia = document.fullscreenElement === figura;
          figura.classList.toggle("diagrama--tela-cheia", cheia);
          if (cheia) zoom.enableMouseWheelZoom();
          window.setTimeout(enquadrar, 50);
        });
        window.addEventListener("beforeprint", enquadrar);
        window.addEventListener("resize", function () { zoom.resize(); });
      })
      .catch(function () {
        // Sem o SVG (ou sem a biblioteca), fica a imagem: o diagrama continua legível.
        figura.dataset.zoom = "indisponivel";
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.svgPanZoom || !window.fetch || !window.DOMParser) return;
    document.querySelectorAll('article img[src*="assets/diagramas/"][src$=".svg"]').forEach(montar);
  });
})();
