# OpenAI Agents instrumentation

## Install

```bash
pip install ollie-sdk "ollie-integrations-openai-agents[agent]"
```

**PyPI not available yet?** See [../docs/customers/install-before-pypi.md](../docs/customers/install-before-pypi.md).

```bash
pip install "git+https://github.com/varunnaganathan/ollie-sdk.git@v0.1.0#egg=ollie-sdk"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.1#subdirectory=openai-agents"
```

## Quick start

```python
from agents import Agent, Runner, function_tool
from ollie_integrations_openai_agents import attach_ollie, create_ollie_client

client = create_ollie_client()
attach_ollie(client, workflow_name="support_bot", flush_mode="ingest")

@function_tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

agent = Agent(name="Assistant", tools=[get_weather], instructions="Be helpful.")
result = Runner.run_sync(agent, "Weather in Paris?")
```

## Credentials

- `OLLIE_API_KEY`, `OLLIE_AGENT_ID` — Ollie
- `OPENAI_API_KEY` — OpenAI (not sent to Ollie)

## Verify

```python
from ollie_integrations_openai_agents import get_last_wire_payload
print(get_last_wire_payload())
```

Start with `flush_mode="validate"`, then `"ingest"`.
