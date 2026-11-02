# Testes ponta a ponta no navegador (Chromium do Playwright), na rede interna do compose.
# A viagem usa o provedor roteiro: nenhum token é gasto.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

RUN pip install --no-cache-dir --break-system-packages "playwright==1.55.0" "pytest>=8,<9"

WORKDIR /e2e
COPY tests ./tests
ENV WEB_URL=http://web
CMD ["pytest", "-v", "tests"]
