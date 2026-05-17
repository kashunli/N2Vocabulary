# Aliyun Model Studio OpenAI-Compatible Notes

Official documentation checked on 2026-05-17:

- OpenAI Chat API reference: https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions
- Model Studio overview and regional base URLs: https://www.alibabacloud.com/help/en/model-studio/what-is-model-studio
- Text-generation model list: https://www.alibabacloud.com/help/en/model-studio/text-generation-model

Key details:

- Use `DASHSCOPE_API_KEY` as the environment variable.
- Beijing OpenAI-compatible full endpoint is `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`.
- SDK-style Beijing base URL is `https://dashscope.aliyuncs.com/compatible-mode/v1`.
- Singapore and US keys use different base URLs from Beijing keys.
- `deepseek-v4-flash` appears in the third-party model table.
- The current model table marks structured output unsupported for `deepseek-v4-flash`; for JSON workflows, prompt for JSON and validate the response instead of assuming `response_format` works.
