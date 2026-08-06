# ollie-integrations

Public packages for Ollie agent-framework integrations. The private Ollie backend monorepo is **not** required for customer installs.

## Packages

| Package | Path | Install pin |
|---------|------|-------------|
| Google ADK | [`google-adk/`](google-adk/) | `@google-adk-v0.3.3#subdirectory=google-adk` |
| OpenAI Agents (Python) | [`openai-agents/`](openai-agents/) | `@openai-agents-v0.2.3#subdirectory=openai-agents` |
| OpenAI Agents (TypeScript) | [`openai-agents-ts/`](openai-agents-ts/) | `#openai-agents-ts-v0.2.2:openai-agents-ts` |

## Instrumentation skills

- **v2 (router — preferred):** [`skills/ollie-instrument-v2/SKILL.md`](skills/ollie-instrument-v2/SKILL.md)  
  Raw: https://raw.githubusercontent.com/varunnaganathan/ollie-integrations/main/skills/ollie-instrument-v2/SKILL.md
- **v1 (fat how-tos):** [`skills/ollie-instrument/SKILL.md`](skills/ollie-instrument/SKILL.md)

One **INSTRUMENTATION.md** per framework (cross-language where applicable). Skill v2 only routes + pins; fetch the doc for how-tos.

### Google ADK

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.2"
pip install "ollie-integrations-google-adk[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@google-adk-v0.3.3#subdirectory=google-adk"
```

### OpenAI Agents (Python)

```bash
pip install "ollie-sdk @ git+https://github.com/varunnaganathan/ollie-sdk.git@v0.3.2"
pip install "ollie-integrations-openai-agents[agent] @ git+https://github.com/varunnaganathan/ollie-integrations.git@openai-agents-v0.2.3#subdirectory=openai-agents"
```

### OpenAI Agents (TypeScript)

```bash
npm install @openai/agents
npm install "github:varunnaganathan/ollie-integrations#openai-agents-ts-v0.2.2:openai-agents-ts"
```
