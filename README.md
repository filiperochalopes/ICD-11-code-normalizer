# icd11-code-normalizer

Microservico minimo em FastAPI para normalizar expressoes ICD-11 pos-coordenadas, gerar um titulo concatenado deterministico e, opcionalmente, produzir uma refraseacao por IA via OpenRouter.

## Stack

- Python 3.12+
- FastAPI
- SQLAlchemy + SQLite
- Typer
- HTTPX
- OpenPyXL
- LangChain + OpenRouter
- Docker / Docker Compose

## Estrutura

```text
app/
  main.py
  api/
  cli/
  core/
  db/
  services/
scripts/
tests/
Dockerfile
docker-compose.yml
requirements.txt
.env.example
```

## Configuracao

1. Copie `.env.example` para `.env`.
2. Gere um bearer token:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
app create-token
```

3. Ajuste `AUTH_TOKEN` no `.env`.

## Seed inicial

Importe a Simple Tabulation oficial da WHO para o SQLite:

```bash
app import-simple-tabulation
```

Ou rode o script direto:

```bash
python scripts/seed_simple_tabulation.py
```

O importador:

- baixa o ZIP oficial;
- encontra o spreadsheet `.xlsx`;
- valida a aba pelos headers esperados;
- carrega apenas linhas com `Code`;
- preserva a ordem fisica da planilha em `sort_key`;
- popula `simple_tabulation_codes`.

## Subindo localmente

```bash
uvicorn app.main:app --reload --port 8000
```

Documentacao automatica: [http://localhost:8000/docs](http://localhost:8000/docs)

## Endpoint principal

`POST /normalize`

Headers:

```http
Authorization: Bearer <TOKEN>
```

Payload de exemplo:

```json
{
  "codes": [
    "XA123&XY456/XT9",
    "AB12&CD34"
  ],
  "include_ai_phrase": true
}
```

Resposta de exemplo:

```json
{
  "results": [
    {
      "input_code": "XA123&XY456/XT9",
      "normalized_code": "XA123/XT9&XY456",
      "title": "Alpha extension / Theta extension + Psi extension",
      "ai_phrase": null,
      "from_cache": false
    }
  ]
}
```

## Docker

Subir a API:

```bash
docker compose up --build
```

Importar a Simple Tabulation dentro do container:

```bash
docker compose run --rm app app import-simple-tabulation
```

## CLI

Comandos disponiveis:

```bash
app import-simple-tabulation
app create-token
app show-config
app healthcheck-db
```

## Testes

```bash
pytest
```

## Observacoes operacionais

- Se `OPENROUTER_API_KEY` nao estiver configurada, a API continua funcionando e retorna apenas `title`.
- O cache do LLM usa `normalized_code`, `title`, `include_ai_phrase`, `model_name` e `prompt_version`.
- Logs de importacao, cache, parsing e tempo de resposta sao enviados para stdout.
