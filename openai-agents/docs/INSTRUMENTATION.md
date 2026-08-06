# OpenAI Agents instrumentation

## Install

```bash
pip install ollie-sdk "ollie-integrations-openai-agents[agent]"
```

**PyPI not available yet?** Install from the public monorepo pin:

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.2#subdirectory=openai-agents"
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

## Custom attributes

### Version capabilities

| Package version | Run attrs (`add_interaction_attributes`) | Span attrs (`add_span_attributes`) |
|-----------------|------------------------------------------|------------------------------------|
| `<=0.2.1` | No | No |
| `0.2.2+` (current pin `openai-agents-v0.2.2`) | Yes — register with `define_feature` | Yes — while the span is open (e.g. inside a `@function_tool`) |

### Run / interaction (0.2.2+)

```python
from ollie_integrations_openai_agents import add_interaction_attributes

client.define_feature(
    "user_tier",
    kind="observable",
    description="Customer plan tier at request time",
)

# While Runner.run / run_sync is in flight:
add_interaction_attributes({"user_tier": "pro", "request_id": "req-1"})
```

### Span properties (0.2.2+)

```python
from ollie_integrations_openai_agents import add_span_attributes

@function_tool
def get_balance(account_id: str) -> dict:
    add_span_attributes({"vendor": "core_ledger", "retry_count": 0})
    return {"balance": 10}
```

Call `add_span_attributes` while the tool/llm/agent span is open (e.g. inside the tool body). No `define_feature` required — values land on span `properties`. Reserved keys (`kind`, `name`, `status`, …) cannot be overwritten.

## Verify

```python
from ollie_integrations_openai_agents import get_last_wire_payload
print(get_last_wire_payload())
```

Start with `flush_mode="validate"`, then `"ingest"`.
