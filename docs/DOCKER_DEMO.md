# Docker Demo

`litflow` is a local engineering-research Copilot MVP. The container packages the application only. It does not contain PDFs, Zotero data, API keys, private raw responses, or the local `outputs/` directory.

## Inputs And Volumes

Set `LITFLOW_DEMO_INPUT_DIR` to a local directory containing the existing LitFlow demo artifacts, including the frozen corpus, Evidence Matrix, author-reviewed writing draft, translation cache, and any historical jobs to browse. The container mounts it read-only at `/app/outputs`.

Offline mode does not create jobs and needs no writable volume. The explicit online profile overlays `/app/outputs/m5_fastapi_v1/jobs` with the named `litflow_jobs` volume so new jobs survive container restarts. It does not copy API keys into the image.

The online profile first runs a one-shot volume initializer that assigns the named job volume to the image's non-root runtime UID/GID `10001`. The actual API container continues to run as `litflow`.

## Offline Demo

Windows PowerShell:

```powershell
$env:LITFLOW_DEMO_INPUT_DIR = (Resolve-Path .\outputs)
$env:LITFLOW_PORT = "8015"
docker compose up --build
```

Linux/macOS:

```bash
export LITFLOW_DEMO_INPUT_DIR="$(pwd)/outputs"
export LITFLOW_PORT=8015
docker compose up --build
```

Open `http://127.0.0.1:8015/`. The default service is `Offline Demo`: it does not read or construct an LLM client. Health check:

```bash
curl http://127.0.0.1:8015/api/v1/health
```

## Explicit Online QA

Online QA may incur provider charges. It is never enabled by the default compose command. Provide credentials only in the launching shell, then select the online profile:

```powershell
$env:LITFLOW_DEMO_INPUT_DIR = (Resolve-Path .\outputs)
$env:LLM_BASE_URL = "https://api.deepseek.com"
$env:LLM_API_KEY = "<set in your shell>"
$env:LLM_MODEL = "deepseek-v4-flash"
docker compose --profile online up --build litflow-online
```

Missing online variables fail closed during compose interpolation or before an online job runs. Do not save keys in compose files, images, screenshots, logs, or the repository.

## Operations

```bash
docker compose logs -f litflow
docker compose down
docker compose --profile online down
docker volume rm research-literature-workflow_litflow_jobs
```

The last command removes only online job persistence. It does not delete the host demo input directory.

## Five-Minute Demo

Use the timed [Local Demo Script](DEMO_SCRIPT.md). It covers the Offline Demo, Q01 provenance, safe failure states, Evidence Matrix, Bilingual Writing Draft, and the bounded online-mode explanation.

## Demo Limits

- This is a local demo, not a public or cloud deployment.
- The QA pilot produced grounded answers for 9/17 answerable queries. Displayed answers were 9/9 author-reviewed as usable.
- Chinese-query machine-translation BM25 Recall@10 was 0.7157 on a 20-query human-reviewed pilot. The mixed-language smoke achieved 5/6 expected-paper Hit@10.
- These are small pilot results, not large-scale benchmark claims. Retrieval and online availability limits remain visible in the UI.
- LitFlow is not an automatic whole-paper or whole-manuscript generator.
