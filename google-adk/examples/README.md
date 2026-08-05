# Sample ADK agent

Optional local smoke test for the integration (not installed in the PyPI wheel).

## Prerequisites

- `pip install -e "integrations/google-adk[agent,dev]"`
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`
- `OLLIE_API_KEY` / `OLLIE_AGENT_ID` (defaults are set when using `--local-only`)

## Run

From `integrations/google-adk/`:

```bash
python -m examples.sample_adk_agent.run --mode single --dump-wire
python -m examples.sample_adk_agent.run --mode sequential --dump-wire
python -m examples.sample_adk_agent.run --mode parallel --dump-wire
python -m examples.sample_adk_agent.run --mode loop --dump-wire
python -m examples.sample_adk_agent.run --mode delegation --dump-wire
```

`--collapse-single-agent` merges a lone agent step into `run`. `--flush-mode ingest` uses a real `ollie.Client()` (requires credentials).

Live pytest (rate limits on free Gemini tier):

```bash
pytest integrations/google-adk/tests -m adk -v
```
