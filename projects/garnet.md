---
type: project
id: garnet
title: garnet
description: Local web-chat personal assistant on AWS Bedrock with read/write tools for Todoist and Jira.
owners: [human:jay.shaffer]
tags: [assistant, bedrock, todoist, jira]
resource: https://github.com/jayshafferpath/garnet
generated:
  by: human:jay.shaffer
  at: 2026-10-12
---

- **Stack:** TypeScript on Node 22 or newer. Fastify 5 serves `public/index.html` on `127.0.0.1:3000`. Other deps: `@aws-sdk/client-bedrock-runtime`, `@doist/todoist-api-typescript`, `jira.js`, zod, pino. Biome and Vitest for tooling.
- **Run:** `cp env.template .env`, then `npm install` and `npm run dev`. `task check` runs typecheck, lint and tests.
- **Code:** the agent loop and tools are in `src/agent/`. Clients are in `src/integrations/{bedrock,jira,todoist}.ts`.
- **External:**
  - Bedrock through the AWS credential chain (`AWS_REGION`, `AWS_PROFILE`, `BEDROCK_MODEL_ID`).
  - Todoist (`TODOIST_API_TOKEN`).
  - Jira basic auth (`JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`). See [jira](../integrations/jira.md).
- **Relationship:** standalone. Its role overlaps with commandcenter's Pearl, but the two share no code.

## Gotchas

- Use the default model id `us.anthropic.claude-sonnet-4-5-20250929-v1:0`. Guessed ids fail with a 400 `ValidationException`.
- `AccessDeniedException` means the active AWS identity lacks Bedrock access. Switch `AWS_PROFILE`.
- Deletes require an explicit confirmation step.
- Chat history is in memory only.
