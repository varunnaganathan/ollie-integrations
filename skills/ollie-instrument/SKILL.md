---
name: ollie-instrument
description: Instrument an AI agent with Ollie — loop until a cloud trace is verified.
---

# Ollie instrumentation

Use when the user is onboarding with Ollie or asks to add tracing.

## Required environment (before the app runs)

Do **not** invent credentials. Use values from onboarding / `.ollie/env.sh` / the customer.

```bash
export OLLIE_API_KEY="..."
export OLLIE_AGENT_ID="..."
```

`create_ollie_client()` / `ollie.Client()` read these from the environment.

## Agent loop

```text
1. Confirm OLLIE_API_KEY + OLLIE_AGENT_ID are set in the same env that runs the app
2. Install the matching package (decision tree below)
3. Apply the smallest attach / workflow patch
4. Run one representative invocation
5. Confirm cloud diagnose / dashboard shows a trace for that agent_id
```

Never mark done without a verified cloud trace.

Onboarding with local instrument check: `flush_mode="validate"` (or `OLLIE_FLUSH_MODE=validate`). Production: `flush_mode="ingest"`.

## Decision tree — which package

### Google ADK

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0"
pip install "ollie-integrations-google-adk[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.2#subdirectory=google-adk"
```

Also need `GOOGLE_API_KEY` or `GEMINI_API_KEY` for the ADK agent (not sent to Ollie).

```python
import os
from ollie_integrations_google_adk import attach_ollie, create_ollie_client

client = create_ollie_client()
attach_ollie(
    client,
    app_name="my_adk_app",  # same string as Runner(app_name=...)
    flush_mode=os.getenv("OLLIE_FLUSH_MODE", "ingest"),
)
# Once at startup, before first Runner.run / run_async.
# Keep create_session → run / run_async. Do not wrap Runner yourself.
```

### Custom Python / other frameworks

Install `ollie-sdk` and follow onboarding docs for `client.workflow` + `ollie.tool`, or the matching `attach_ollie` package when published under this monorepo.
