# ollie-integrations

Public packages for Ollie agent-framework integrations. The private Ollie backend monorepo is **not** required for customer installs.

## Packages

| Package | Path | Install pin |
|---------|------|-------------|
| Google ADK | [`google-adk/`](google-adk/) | `@google-adk-v0.3.2#subdirectory=google-adk` |
| OpenAI Agents | [`openai-agents/`](openai-agents/) | `@openai-agents-v0.2.1#subdirectory=openai-agents` |

### Google ADK

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0"
pip install "ollie-integrations-google-adk[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.2#subdirectory=google-adk"
```

## Instrumentation skill (one copy)

Follow [`skills/ollie-instrument/SKILL.md`](skills/ollie-instrument/SKILL.md) in Cursor or Claude Code.

Raw: https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/main/skills/ollie-instrument/SKILL.md

### OpenAI Agents

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.0"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.1#subdirectory=openai-agents"
```

