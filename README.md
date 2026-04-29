# ADA Pulse 2026

Short working repository for Assignment 2 implementation of the Pulse architecture.

## Project Structure

```text
ada-pulse-2026/
  app/
    infra/                    # Shared infra scripts (upload, setup, triggers)
    kpi-analytics/            # KPI compute, serving API, MCP server
    operational-intelligence/ # Agents
    reporting-delivery/       # Report composition and delivery
  data/
    mockaroo/                 # Raw generated source CSVs
    ingest/                   # Cleaned ingest-ready CSVs
  docs/                       # Assignment docs and implementation plans
  scripts/                    # Utility scripts (data prep, etc.)
  pyproject.toml
```

## Python Environment (uv)

```bash
uv venv
source .venv/bin/activate
uv sync
```

Run Python scripts with:

```bash
uv run python scripts/create_mock_data.py
```

## GCloud Quick Tips

Check active account and project before running any upload/deploy command:

```bash
gcloud auth list
gcloud config get-value project
gcloud config list
```

Set the correct project:

```bash
gcloud config set project ada26-pulse-project
```

If needed, set the active account:

```bash
gcloud config set account <your-email>
```

For Python client libraries (ADC), make sure credentials are set and quota project matches:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project ada26-pulse-project
```

## Notes

- Nothing Yet
