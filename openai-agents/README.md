# ollie-integrations-openai-agents

Single-`run` Ollie integration for the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python).

```python
from ollie_integrations_openai_agents import attach_ollie, create_ollie_client

client = create_ollie_client()
attach_ollie(client, workflow_name="my_app", flush_mode="ingest")

# Runner.run / Runner.run_sync are traced automatically
```

See [docs/INSTRUMENTATION.md](docs/INSTRUMENTATION.md) and [../WORKFLOW_INTERACTION_MODEL.md](../WORKFLOW_INTERACTION_MODEL.md).
