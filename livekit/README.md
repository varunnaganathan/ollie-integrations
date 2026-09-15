# ollie-integrations-livekit

Native [LiveKit Agents](https://github.com/livekit/agents) integration for Ollie Sentry. Observes voice pipeline stages—STT, turn detection, agent, tools, and TTS—and delivers Ollie v2 interaction traces—no mapping configuration required.

## Documentation

- **[Instrumentation guide](docs/INSTRUMENTATION.md)** — install, configure, integrate, and deploy
- [Execution model](docs/EXECUTION_MODEL.md) — span types and example tree
- [Hooks reference](docs/HOOKS.md) — API and event wiring

## Quick start

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.4"
pip install "ollie-integrations-livekit[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@livekit-v0.2.0#subdirectory=livekit"
```

```python
import ollie
from ollie_integrations_livekit import attach_ollie

client = ollie.Client()
attach_ollie(client, app_name="voice_support", flush_mode="ingest")

# Run your existing AgentSession — instrumentation is automatic
```

See the [instrumentation guide](docs/INSTRUMENTATION.md) for credentials, environment variables, and deployment.
