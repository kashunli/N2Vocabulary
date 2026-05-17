---
name: aliyun-openai-compatible-api
description: Call Alibaba Cloud Model Studio / DashScope models through the OpenAI-compatible chat completions API. Use when a workflow needs Qwen, DeepSeek, Kimi, GLM, or other Aliyun-hosted models with DASHSCOPE_API_KEY, regional base URLs, JSON-only prompting, retry handling, or standard-library HTTP calls.
---

# Aliyun OpenAI-Compatible API

Use this skill when a project script needs Alibaba Cloud Model Studio / DashScope through the OpenAI-compatible chat completions interface.

## Defaults

- Environment key: `DASHSCOPE_API_KEY`
- China Beijing base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- Chat endpoint: `/chat/completions`
- Full Beijing URL: `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
- Header: `Authorization: Bearer $DASHSCOPE_API_KEY`
- Good default model for the current N2 translation fill: `deepseek-v4-flash`

Region base URLs are not interchangeable with API keys. Use the region that matches the key:

- Singapore: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- US Virginia: `https://dashscope-us.aliyuncs.com/compatible-mode/v1`
- China Beijing: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- China Hong Kong: `https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1`

## Request Pattern

Prefer a normal chat-completions body:

```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "system", "content": "Return valid JSON only."},
    {"role": "user", "content": "..."}
  ],
  "temperature": 0.1
}
```

For `deepseek-v4-flash`, do not rely on OpenAI `response_format` by default: Aliyun's current model table marks structured output unsupported for that third-party model. Ask for JSON in the prompt, parse strictly, and retry malformed responses.

## Operational Rules

1. Never store API keys in the repo or generated output.
2. Check `DASHSCOPE_API_KEY` before calling the API, but only print whether it is present.
3. Keep prompts and batch outputs reviewable when updating durable learning data.
4. Use small trial batches before a full run.
5. For one-time database updates, write selected records, batch JSON, a manifest, and an apply summary.
6. Retry transient HTTP failures and invalid JSON; keep already-written batch files for resume.

## Official References

Load `references/model_studio_openai_compat.md` when adjusting endpoint, region, model, or request shape.
