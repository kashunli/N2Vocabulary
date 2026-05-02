# DeepSeek API Notes

DeepSeek's official API docs describe an OpenAI-compatible chat endpoint.

Defaults for this skill:

- Base URL: `https://api.deepseek.com`
- Full URL: `https://api.deepseek.com/chat/completions`
- Model: `deepseek-v4-flash`
- API key env var: `DEEPSEEK_API_KEY`; read from current process env first, then Windows User env, then Windows Machine env.
- Non-thinking mode: `"thinking": {"type": "disabled"}`
- JSON mode: `"response_format": {"type": "json_object"}`

Request body shape:

```json
{
  "model": "deepseek-v4-flash",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."}
  ],
  "thinking": {"type": "disabled"},
  "response_format": {"type": "json_object"},
  "temperature": 0.2
}
```

The script uses only Python standard library modules, so it does not require installing the OpenAI SDK.
