// Os links de volta à demo (/ e /mapa) saem dos bastidores para a aba inteira: no painel
// lateral da demo, o capítulo roda num iframe, e a demo não deve abrir dentro dele.
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll('a[href="/"], a[href="/mapa"]').forEach(function (link) {
    link.target = "_top";
  });
});
