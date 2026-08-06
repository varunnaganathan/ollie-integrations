# ollie-integrations-google-adk

Native [Google ADK](https://github.com/google/adk-python) integration for Ollie Sentry. Captures ADK execution and emits normalized Ollie v2 traces: **one `run` interaction** per `Runner.run_async` with tool/LLM/agent spans in `events.spans` — no mapping configuration required.

## Documentation

- **[Instrumentation guide](docs/INSTRUMENTATION.md)** — install, configure, integrate, and deploy
- [Execution model](docs/EXECUTION_MODEL.md) — span types and events
- [Hooks reference](docs/HOOKS.md) — API and hook points

## Quick start

```bash
pip install ollie-sdk "ollie-integrations-google-adk[agent]"
```

```python
import ollie
from ollie_integrations_google_adk import attach_ollie

client = ollie.Client()
attach_ollie(client, app_name="my_adk_app", flush_mode="ingest")

# Run your existing Runner.run_async — instrumentation is automatic
```

See the [instrumentation guide](docs/INSTRUMENTATION.md) for credentials, environment variables, and deployment.
