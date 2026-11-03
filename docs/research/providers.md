# Model-provider API research

All pages below were read on **2026-11-02**, from the provider's own documentation site. Facts marked
**UNVERIFIED** could not be confirmed on an official page and must be checked again before the adapter
relies on them. No authenticated calls were made.

Model names appear here only when a doc page used them as an example. Adapters must not hardcode them:
models come from discovery (listing endpoint) or from the admin-editable catalog.

Shorthand: "OpenAI-compatible" means the provider accepts the Chat Completions shape
(`POST {base}/chat/completions`, `messages`, `choices[].message|delta`, SSE `data:` chunks ending in
`data: [DONE]`).

---

## 1. OpenAI API (`openai_api`)

Sources:
- Chat create: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
- Overview (auth, headers): https://developers.openai.com/api/reference/overview
- Models list: https://developers.openai.com/api/reference/resources/models/methods/list
- Error codes: https://developers.openai.com/api/docs/guides/error-codes
- Rate limits: https://developers.openai.com/api/docs/guides/rate-limits
- Migrate to Responses: https://developers.openai.com/api/docs/guides/migrate-to-responses
- Deprecations: https://developers.openai.com/api/docs/deprecations

1. **Base URL:** `https://api.openai.com/v1`. There are no regions to choose.
2. **Auth:** `Authorization: Bearer <key>`. The optional headers `OpenAI-Organization` and `OpenAI-Project` pick the org and project. The response header `x-request-id` identifies the request. The optional request header `X-Client-Request-Id` must be ASCII, at most 512 characters and unique, or the request returns 400.
3. **Chat:** `POST /chat/completions`, with `model` and `messages` required.
   - Roles: `developer`, `system`, `user`, `assistant`, `tool`. `function` is deprecated, and `developer` replaces `system` for o1 and newer models.
   - Deprecated parameters: `max_tokens` (use `max_completion_tokens`; o-series models reject `max_tokens`), `functions`/`function_call` (use `tools`/`tool_choice`), and `user` (use `safety_identifier` and `prompt_cache_key`).
4. **Models:** `GET /models` returns `{"object":"list","data":[{"id","object":"model","created","owned_by"}]}`. Each entry may also carry an optional `shutdown_date`.
5. **Streaming:** SSE `data:` lines, each holding a `chat.completion.chunk`, and the stream ends with `data: [DONE]`.
   - `stream_options.include_usage: true` adds one last chunk with `choices: []` and the `usage`, sent just before `[DONE]`.
   - The docs warn this chunk may never arrive if the stream is interrupted.
6. **JSON and tools:**
   - `response_format` accepts `text`, `json_object` (the older JSON mode) or `json_schema` (with `strict`). The docs prefer `json_schema` where the model supports it.
   - `tools` accepts `function` tools (with `strict`) and `custom` tools.
   - `tool_choice` accepts `none`, `auto`, `required`, or a named or allowed-tools object.
7. **Usage fields:** `prompt_tokens`, `completion_tokens`, `total_tokens`.
   - `prompt_tokens_details` holds `cached_tokens` and `cache_write_tokens`, among others.
   - `completion_tokens_details` holds `reasoning_tokens`, among others.
8. **Errors:** the body carries `error.message`, `error.type`, `error.param` and `error.code`. The docs reference these fields but show no full schema, so the exact shape is **UNVERIFIED** beyond that.
   - **401:** bad key, wrong org, or an IP outside the allowlist. **403:** unsupported region. **500:** server error. **503** `server_is_overloaded`: retry, honouring `Retry-After`.
   - **429** covers both rate limits and quota. Tell them apart by `error.code`:
     - Rate limit (retryable): a plain request or token rate limit, or `rate_limit_error` with code `slow_down` (traffic ramped up too fast).
     - Quota (not retryable): `credit_balance_exhausted`, `organization_spend_limit_exceeded`, `project_spend_limit_exceeded`, `organization_usage_limit_exceeded`. Here `error.type` can still be `insufficient_quota`. The docs say: "Retrying billing, spend, or quota errors won't restore API access."
   - Rate-limit headers: `x-ratelimit-{limit,remaining,reset}-{requests,tokens}`, plus `x-ratelimit-*-project-tokens` when a project token limit applies. `Retry-After` may appear on temporary 429s and 503s.
9. **Deprecations:**
   - The Chat Completions page opens with "We recommend trying Responses…". The migration guide says "Chat Completions remains supported… Responses is recommended for all new projects." Neither page gives a sunset date.
   - The Assistants API was sunset on **2026-08-26**.
   - **Choice:** Chat Completions is still a safe common denominator across all eight providers. Responses (`/v1/responses`) is the long-term OpenAI path.

## 2. Anthropic API (`anthropic_api`)

Sources:
- Overview: https://platform.claude.com/docs/en/api/overview
- Versions: https://platform.claude.com/docs/en/api/versioning
- Messages create: https://platform.claude.com/docs/en/api/messages/create
- Models list: https://platform.claude.com/docs/en/api/models/list
- Streaming: https://platform.claude.com/docs/en/build-with-claude/streaming
- Errors: https://platform.claude.com/docs/en/api/errors
- Rate limits: https://platform.claude.com/docs/en/api/rate-limits
- Structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs

The old domain `docs.anthropic.com` now 301-redirects to `platform.claude.com/docs`.

1. **Base URL:** `https://api.anthropic.com`. There is no regional base URL. Requests may set `inference_geo` (for example `"us"` or `"global"`), and all geos share one rate-limit pool.
2. **Auth:** `Authorization: Bearer <key>` is now the primary header. `x-api-key: <key>` is documented as a "Legacy fallback… still supported".
   - Required: `anthropic-version` and `content-type: application/json`.
   - `anthropic-workspace-id` is required when the key is not scoped to a workspace.
   - **Current `anthropic-version` values: `2026-10-21` (latest, recommended) and `2023-06-01`.**
   - `2026-10-21` breaks some requests. The Messages API now returns 400 when a request sends `temperature`, `top_p` or `top_k`, on every model. It also returns 400 for a `document` block in an assistant message, and for a user `text` block with non-empty `citations`.
   - Pinning `2023-06-01` keeps the older behaviour. The docs show no sunset date for it.
3. **Chat:** `POST /v1/messages`, with `model`, `max_tokens` and `messages` required. This is **not** OpenAI-compatible.
   - `system` is a top-level field, a string or an array of text blocks.
   - Each tool is `{name, description, input_schema, strict?}`.
   - `tool_choice` takes `auto`, `any`, `tool` (by name) or `none`.
   - The response is `content[]`, a list of blocks: `text`, `thinking`, `redacted_thinking`, `tool_use`, server-tool blocks and more.
   - `stop_reason` is one of `end_turn`, `max_tokens`, `stop_sequence`, `tool_use`, `pause_turn`, `refusal`, `model_context_window_exceeded`.
   - Some newer models refuse certain options with a 400:
     - Forced tool choice (`any` or `tool`).
     - Assistant prefill.
     - `thinking: {type: "enabled"}`, on 4.7+ models, which only take `adaptive`.
   - The adapter should read the model's `capabilities` before sending these options (see the next item).
4. **Models:** `GET /v1/models`.
   - Query parameters: `limit` (1–1000, default 20), `after_id`, `before_id`, and `lifecycle[]` (`active`, `deprecated` or `retired`; the default returns active plus deprecated).
   - The response is `{data:[ModelInfo], first_id, last_id, has_more}`.
   - Each `ModelInfo` has `id`, `type:"model"`, `display_name`, `created_at`, `lifecycle`, `deprecated_at`, `retires_at`, `line`, `max_input_tokens`, `max_tokens`, and a `capabilities` object. The capabilities include `structured_outputs`, `thinking.types.*`, `effort.*`, `image_input`, `pdf_input`, `batch` and `citations`.
   - This is the richest discovery endpoint of all eight providers.
5. **Streaming:** `"stream": true` returns **named** SSE events, as `event: <type>` followed by `data: {...}`.
   - Order: `message_start`, then per content block `content_block_start`, one or more `content_block_delta`, and `content_block_stop`; then one or more `message_delta`, then `message_stop`.
   - Delta types: `text_delta`, `input_json_delta` (tool input as `partial_json`), `thinking_delta`, `signature_delta`, `citations_delta`.
   - `ping` events can arrive at any point.
   - A mid-stream error arrives as `event: error` with `data: {"type":"error","error":{"type":"overloaded_error",...}}`.
   - **There is no `[DONE]`**. Version `2023-06-01` removed it.
   - Usage: `message_start.message.usage` holds the input counts, and `message_delta.usage` holds the **cumulative** counts.
   - The docs say unknown event types must be ignored gracefully.
6. **JSON and tools:**
   - Structured output uses `output_config.format = {"type":"json_schema","schema":{...}}` and needs no beta header. The old `output_format` parameter is deprecated and needs `structured-outputs-2025-11-13`.
   - Schema limits (a 400 otherwise): no recursion, no numeric or string length constraints, and `additionalProperties` must be `false`.
   - A refusal can still return 200 with output that does not match the schema (`stop_reason: "refusal"`).
   - Strict tool use: set `strict: true` on a tool.
7. **Usage fields:** `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_creation.{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}`, `output_tokens_details.thinking_tokens`, `server_tool_use`, `service_tier`, `inference_geo`, `speed`.
   - Total input = `input_tokens` + `cache_creation_input_tokens` + `cache_read_input_tokens`.
8. **Errors:** the body is `{"type":"error","error":{"type","message"},"request_id"}`, and the response header `request-id` carries the same ID.
   - 400 `invalid_request_error`. This also covers a **user-set spend limit**: the message starts with "You have reached your specified API usage limits".
   - 401 `authentication_error`. 402 `billing_error`. 403 `permission_error`. 404 `not_found_error`. 409 `conflict_error`. 413 `request_too_large`. 429 `rate_limit_error`. 500 `api_error`. 504 `timeout_error`. 529 `overloaded_error`.
   - A 429 is one of three things:
     - **Rate limit** (retryable): has a `retry-after` header.
     - **Acceleration limit**: also 429.
     - **Tier monthly spend cap** (not retryable): no `retry-after`, and `error.details.error_code = "enforced_spend_limit_reached"`.
   - 529 means the whole API is overloaded. It is transient and global, not tied to your account.
   - Rate-limit headers: `anthropic-ratelimit-{requests,tokens,input-tokens,output-tokens}-{limit,remaining,reset}`.
9. **Deprecations:**
   - `x-api-key` is now called legacy (still supported).
   - `anthropic-version: 2026-10-21` removes the sampling parameters, so the adapter must not send `temperature` or `top_p` under it.
   - The model enum on the Messages page lists deprecations, for example the `claude-sonnet-4-5` end-of-life on 2026-11-30. The `lifecycle` and `retires_at` fields from `/v1/models` carry the same information in machine-readable form.

## 3. DeepSeek (`deepseek_api`)

Sources:
- Home: https://api-docs.deepseek.com/
- Chat completion: https://api-docs.deepseek.com/api/create-chat-completion
- List models: https://api-docs.deepseek.com/api/list-models
- Error codes: https://api-docs.deepseek.com/quick_start/error_codes
- Rate limit: https://api-docs.deepseek.com/quick_start/rate_limit
- JSON mode: https://api-docs.deepseek.com/guides/json_mode
- Anthropic API: https://api-docs.deepseek.com/guides/anthropic_api

1. **Base URLs:**
   - OpenAI format: `https://api.deepseek.com`, with chat at `https://api.deepseek.com/chat/completions`.
   - Beta features (`prefix`, `reasoning_content` as input): `https://api.deepseek.com/beta`.
   - Anthropic format: `https://api.deepseek.com/anthropic`.
   - There is no regional variant.
2. **Auth:** `Authorization: Bearer <key>`. On the Anthropic endpoint, `x-api-key` also works, and `anthropic-version` is ignored there.
3. **Chat:** OpenAI-compatible `POST /chat/completions`. Deviations:
   - `thinking: {type: enabled|disabled}` and `reasoning_effort` (`none`, `low`, `high`, `max`). `thinking` wins over `reasoning_effort` when both are sent.
   - `frequency_penalty` and `presence_penalty` are "no longer supported" and silently ignored.
   - `temperature` has no effect in thinking mode, and `top_p` is ignored in some model/mode combinations.
   - `tool_choice: required` and named tool choice return 400 in thinking mode.
   - `stream_options` without `stream: true` returns 400.
   - The response adds `message.reasoning_content` (streamed as `delta.reasoning_content`).
4. **Models:** `GET /models` returns `{object:"list", data:[{id, object:"model", owned_by, name?, context_window?, max_output_tokens?, input_modalities?, output_modalities?, effort?{supported_levels, default_level}, api_capabilities?}]}`.
   - The metadata fields may be absent, so treat them as optional.
5. **Streaming:**
   - SSE `data:` lines, ending with `data: [DONE]`.
   - With `include_usage`, every chunk carries `usage: null` except the **last content chunk**, which carries the usage and still has one choice with a non-null `finish_reason`. There is no separate usage-only chunk, unlike OpenAI.
   - **Keep-alive quirk:** while a request waits in the queue, DeepSeek sends **empty lines** (non-streaming) or **`: keep-alive` SSE comments** (streaming). A hand-written parser must skip both.
   - If inference has not started after 10 minutes, the server closes the connection.
6. **JSON and tools:**
   - `response_format` accepts only `text` or `json_object`. There is **no `json_schema`**.
   - JSON mode needs the word "json" in the prompt. Invalid JSON can come back as **blank content** with `finish_reason: stop`.
   - `tools` accepts function tools only. `strict` is a beta feature.
7. **Usage fields:** `prompt_tokens`, `completion_tokens`, `total_tokens`, `prompt_tokens_details.cached_tokens`, `prompt_cache_hit_tokens`, `prompt_cache_miss_tokens`, `completion_tokens_details.reasoning_tokens`.
   - `prompt_tokens` = hit + miss.
8. **Errors:** 400 bad format, 401 auth, **402 Insufficient Balance** ("You have run out of balance"), 422 invalid parameters, **429 Rate Limit Reached** (too fast, or over the concurrency/QPS limit), 500 server error, 503 server overloaded.
   - Quota is 402, rate limit is 429, so the two are unambiguous.
   - Rate limits are concurrency-based and counted per account across all keys.
   - The error JSON body shape is **UNVERIFIED** (not shown on the page). It is presumably the OpenAI-style `{"error":{...}}`.
9. **Deprecations:** older model names are still accepted, but "the corresponding models have been retired" and requests to them are routed to the current model. Do not trust a cached model ID; re-run discovery.

## 4. Z.ai / GLM (`zai_glm_api`)

Sources:
- API intro: https://docs.z.ai/api-reference/introduction
- Chat: https://docs.z.ai/api-reference/llm/chat-completion
- Errors: https://docs.z.ai/api-reference/api-code
- Streaming guide: https://docs.z.ai/guides/capabilities/streaming
- Structured output: https://docs.z.ai/guides/capabilities/struct-output
- Coding Plan: https://docs.z.ai/devpack/quick-start
- Docs index: https://docs.z.ai/llms.txt
- Mainland intro: https://docs.bigmodel.cn/cn/api/introduction
- Mainland Coding Plan: https://docs.bigmodel.cn/cn/coding-plan/quick-start
- Mainland docs index: https://docs.bigmodel.cn/llms.txt

1. **Base URLs:** Z.ai is the international site and bigmodel.cn is mainland China. Each site issues its own keys; the docs do not say whether the two sites share keys (**UNVERIFIED**, so assume they do not).

   | Use | International | Mainland |
   |---|---|---|
   | General API (OpenAI-style) | `https://api.z.ai/api/paas/v4` | `https://open.bigmodel.cn/api/paas/v4` |
   | Coding Plan, Chat Completions | `https://api.z.ai/api/coding/paas/v4` | `https://open.bigmodel.cn/api/coding/paas/v4` |
   | Coding Plan, Anthropic Messages | `https://api.z.ai/api/anthropic` | `https://open.bigmodel.cn/api/anthropic` |
   | Coding Plan, Responses | `https://api.z.ai/api/v1` | `https://open.bigmodel.cn/api/v1` |

   A Coding Plan subscription must use the coding endpoints.
2. **Auth:** `Authorization: Bearer <key>`. The current docs do not mention a JWT alternative.
3. **Chat:** `POST {base}/chat/completions`, effectively OpenAI-compatible: the docs show the OpenAI SDKs pointed at the base URL, though they never say "compatible". Deviations:
   - **`tool_choice` accepts only `"auto"`.**
   - `stop` takes at most one word ("Currently, only one stop word is supported").
   - `temperature` is limited to [0, 1], and `top_p` to [0.01, 1].
   - `do_sample` is an extra field; when false, sampling parameters are ignored.
   - `thinking: {type, clear_thinking}` and `reasoning_effort` are supported.
   - `tool_stream` streams tool-call arguments.
   - `tools` also accepts the `retrieval` and `web_search` types.
   - The response adds `request_id` and `web_search`. Extra `finish_reason` values: `sensitive`, `network_error`, `model_context_window_exceeded`.
4. **Models:** **no listing endpoint is documented.** Neither docs index (z.ai nor bigmodel.cn) has a models page, so this provider needs the admin catalog. An OpenAI-style `GET /models` may still exist undocumented (**UNVERIFIED**).
5. **Streaming:**
   - SSE `data:` chunks, ending with `data: [DONE]`.
   - `usage` "only appears in the last chunk", the one with `finish_reason: "stop"`.
   - `stream_options` / `include_usage` is **not documented**. Do not send it unless a test proves it is accepted.
   - If inference ends abnormally mid-stream, the error codes may not be sent; the reason shows up in `finish_reason` instead.
6. **JSON and tools:**
   - `response_format` accepts `text` or `json_object`. **There is no `json_schema`**: the guide puts the schema in the prompt and validates the output on the client.
   - Function tools are supported, up to 128 per request.
7. **Usage fields:** `prompt_tokens`, `completion_tokens`, `total_tokens`, `prompt_tokens_details.cached_tokens`.
8. **Errors:** the body is `{"error":{"code":"<business code string>","message":"..."}}`, and the HTTP status is separate. **Every quota error is HTTP 429**, so the adapter has to switch on `error.code`:
   - **Rate limit or overload (retryable):** `1302` "Rate limit reached for requests"; `1305` "service may be temporarily overloaded".
   - **Balance or quota (not retryable until reset or top-up):**
     - `1113` "Insufficient balance or no resource package. Please recharge."
     - `1308` usage limit, resets at `{next_flush_time}`.
     - `1309` Coding Plan expired.
     - `1310` weekly or monthly limit exhausted.
     - `1311` the plan does not include the model.
     - `1313` fair-use throttling.
     - `1314` enterprise package expired.
     - `1316`–`1321`: 5-hour or 7-day limits, with no extra usage available.
   - Other codes: 401 (`1000`–`1005`), 400 (`1210`–`1215`, `1221` API offline, `1261` prompt too long, `1301` unsafe content), 403 (`1220`), 500 (`1200`, `1230`, `1234`).
   - The rate-limit page `docs.z.ai/api-reference/rate-limit` redirects to a console page that needs a login, so the actual limits are **UNVERIFIED**.
9. **Deprecations:** error `1221` "API has been taken offline" exists. No endpoint deprecation notice was found.

## 5. Moonshot AI / Kimi (`moonshot_kimi_api`)

Sources:
- International chat: https://platform.kimi.ai/docs/api/chat
- International models: https://platform.kimi.ai/docs/api/list-models
- International errors: https://platform.kimi.ai/docs/api/errors
- China chat: https://platform.kimi.com/docs/api/chat
- China models: https://platform.kimi.com/docs/api/list-models

The old docs domains now redirect: `platform.moonshot.ai` goes to `platform.kimi.ai` (international), and `platform.moonshot.cn` goes to `platform.kimi.com` (China).

1. **Base URLs:** international `https://api.moonshot.ai/v1`; China `https://api.moonshot.cn/v1`.
   - **Keys are not interchangeable** between `platform.kimi.ai` and `platform.kimi.com`. A key used on the wrong platform returns 401.
2. **Auth:** `Authorization: Bearer <MOONSHOT_API_KEY>`.
3. **Chat:** `POST /v1/chat/completions`, OpenAI-compatible in practice: the docs use the OpenAI SDKs and the OpenAI response and stream shapes, though they never use the word "compatible".
   - Extras: `thinking: {type, keep}` on some K2 models, `reasoning_effort` (`low`, `high`, `max`) on K3, `max_completion_tokens`, `prompt_cache_key`, `prompt_cache_options`, `prediction`, `safety_identifier`.
   - Reasoning arrives in `delta.reasoning_content`, before `content`.
   - The chat page does not document `temperature` or `n`.
4. **Models:** `GET /v1/models` returns `{object:"list", data:[{id, object:"model", created, owned_by, context_length, supports_image_in, supports_video_in, supports_reasoning}]}`. The docs recommend calling it before chatting.
5. **Streaming:**
   - SSE `data:` lines holding `chat.completion.chunk`, ending with `data: [DONE]`.
   - With `stream_options.include_usage: true`, the chunk just before `[DONE]` has `choices: []` and the usage, as in OpenAI. That chunk may be lost if the stream is interrupted.
6. **JSON and tools:**
   - `response_format` accepts `text`, `json_object` and **`json_schema`** (`json_schema.name` and `schema` are required; `strict` defaults to true).
   - `tools` accepts function tools, with `strict` defaulting to true.
   - `tool_choice` accepts `auto`, `none`, `required` or a named function.
7. **Usage fields:** `prompt_tokens`, `completion_tokens` (reasoning included), `total_tokens`, top-level `cached_tokens`, `prompt_tokens_details.cached_tokens`, `prompt_tokens_details.cache_write_tokens`, `completion_tokens_details.reasoning_tokens` (the last one appears in examples only).
   - The cached, cache-write and uncached counts "sum to `prompt_tokens`".
8. **Errors:** the body is `{"error":{"message","type","code"}}`. Switch on `error.type`:
   - 400: `invalid_request_error`, `content_filter`.
   - 401: `invalid_authentication_error`, `incorrect_api_key_error`.
   - 403: `permission_denied_error` (also used for the IP allowlist).
   - 404: `resource_not_found_error`.
   - **429 has three meanings:**
     - `rate_limit_reached_error`: concurrency, RPM, TPM or TPD. Retryable, or wait for the next day for TPD.
     - **`exceeded_current_quota_error`**: insufficient balance, disabled account, or token quota used up. Not retryable.
     - `engine_overloaded_error`: server capacity. Retry with `Retry-After` and backoff; topping up does not help.
   - 499 `client_closed_request`. 500 `server_error` / `unexpected_output`. 503 `server_unavailable`. 504 means no response after 900 s, so use streaming for long requests.
   - The docs note that the OpenAI SDK's automatic retries count against the rate limit.
9. **Deprecations:** no endpoint deprecation was found. Only the docs domains moved to `kimi.*`; the API hosts stay on `moonshot.*`.

## 6. Alibaba Cloud Model Studio / Qwen (`qwen_api`)

Sources:
- OpenAI-compatible chat: https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions
- Compatibility overview: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- Regions: https://www.alibabacloud.com/help/en/model-studio/regions/
- Error codes: https://www.alibabacloud.com/help/en/model-studio/error-code

1. **Base URLs (OpenAI-compatible mode).** The **workspace-dedicated domain** is now the primary form: `https://{WorkspaceId}.{region}.maas.aliyuncs.com/compatible-mode/v1`. The native DashScope API lives at the same host under `/api/v1`.

   | Region (id) | Workspace-dedicated host | Legacy DashScope domain |
   |---|---|---|
   | China, Beijing (`cn-beijing`) | `{WorkspaceId}.cn-beijing.maas.aliyuncs.com` | `dashscope.aliyuncs.com` |
   | Singapore (`ap-southeast-1`) | `{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com` | `dashscope-intl.aliyuncs.com` |
   | US, Virginia (`us-east-1`) | `{WorkspaceId}.us-east-1.maas.aliyuncs.com` | not supported |
   | Germany, Frankfurt (`eu-central-1`) | `{WorkspaceId}.eu-central-1.maas.aliyuncs.com` | not supported |
   | Japan, Tokyo (`ap-northeast-1`) | `{WorkspaceId}.ap-northeast-1.maas.aliyuncs.com` | not supported |
   | China, Hong Kong (`cn-hongkong`) | `{WorkspaceId}.cn-hongkong.maas.aliyuncs.com` | `cn-hongkong.dashscope.aliyuncs.com` |

   - Append `/compatible-mode/v1` to any host in the table.
   - **Selecting region and workspace.** The base URL selects both, and `{WorkspaceId}` is a subdomain, not a header or a parameter.
     - "Each region has its own endpoint, API Key, and model list. These cannot be used across regions." A key used in the wrong region returns 401.
     - Frankfurt, Tokyo, Hong Kong and Virginia **require** you to create a workspace and pick a deployment scope first. The scopes are Global, EU, Japan, Hong Kong and US.
     - A workspace domain reaches only its own workspace, while the legacy DashScope domain reaches all of them.
     - The full host can be copied from the console's Workspace Management page.
     - The compatibility overview tells users to migrate from the legacy domains to the workspace domains.
   - **Doc inconsistency:** the compatibility overview shows the `ap-southeast-1` host for Beijing. The chat reference and the regions page say `cn-beijing`, which is the one to use.
   - The NFactory config should store region and workspace ID, or the whole base URL as an admin-editable value.
2. **Auth:** `Authorization: Bearer <DASHSCOPE_API_KEY>`.
3. **Chat:** OpenAI-compatible `POST {base}/chat/completions`. Deviations:
   - `enable_thinking` is non-standard. Over raw HTTP it goes at the top level of the body; the OpenAI SDK passes it through `extra_body`.
   - `tool_choice: "required"` is **not supported by Qwen models**, and a named function is not supported in thinking mode.
   - `parallel_tool_calls` defaults to true.
   - `n` only works on some models.
   - The system message must be `messages[0]`.
   - Reasoning arrives in `reasoning_content`.
   - Some models reject HTTP calls ("current user api does not support http call").
   - The older overview says "tools cannot be used with stream=True". The newer chat reference does not repeat this, so the restriction is **UNVERIFIED** for current models.
4. **Models:** **no documented listing endpoint** in compatible mode. `GET /compatible-mode/v1/models` is **UNVERIFIED**. The model list is a docs page that differs per region, so use the admin catalog.
5. **Streaming:**
   - SSE `data:` chunks, ending with `data: [DONE]` (as the HTTP example shows).
   - With `stream_options.include_usage: true`, a last chunk with `choices: []` carries the usage, and earlier chunks have `usage: null`. This matches OpenAI.
6. **JSON and tools:**
   - `response_format` accepts `text`, `json_object` (the prompt must ask for JSON, or the call errors) and **`json_schema`** (`name`, `schema`, `strict`). Model support differs between the two modes.
   - Function tools are supported.
7. **Usage fields:** `prompt_tokens`, `completion_tokens`, `total_tokens`, `prompt_tokens_details.cached_tokens`, `completion_tokens_details.{reasoning_tokens, text_tokens}`. `text_tokens` includes the reasoning tokens.
8. **Errors:** the error JSON shape in compatible mode is **UNVERIFIED**; the error-code page lists only `HTTP-code` pairs.
   - **Rate limit (retryable):**
     - `429 Throttling`.
     - `429 Throttling.RateQuota` / `limit_requests` (RPS or RPM).
     - **`429 Throttling.AllocationQuota` / `insufficient_quota`**, which means **TPS/TPM exceeded**. Despite the name, this is a rate limit, not a balance problem.
     - 500/503 `ServiceUnavailable` (capacity).
   - **Balance or billing (not retryable):**
     - `400 Arrearage`: overdue payment.
     - `429 PostpaidBillOverdue`, `429 PrepaidBillOverdue`.
     - `isv.OUT_OF_SERVICE`: insufficient balance.
     - `403 AllocationQuota.FreeTierOnly`: free tier used up.
     - The `429 Throttling.AllocationQuota` row with the message "Free allocated quota exceeded".
   - Coding Plan messages: "hour", "week", "month", "concurrency" and "usage allocated quota exceeded".
   - So the adapter must look at **code and message together**, never the HTTP status alone.
9. **Deprecations:** the legacy `dashscope*.aliyuncs.com` domains are to be migrated to the workspace-dedicated domains. No sunset date was given.

## 7. MiniMax (`minimax_api`)

Sources:
- OpenAI-compatible: https://platform.minimax.io/docs/api-reference/text-openai-api
- Native chat: https://platform.minimax.io/docs/api-reference/text-post
- Anthropic-compatible: https://platform.minimax.io/docs/api-reference/text-anthropic-api
- Models: https://platform.minimax.io/docs/api-reference/models/openai/list-models
- Error codes: https://platform.minimax.io/docs/api-reference/errorcode
- China, OpenAI-compatible: https://platform.minimax.cn/docs/api-reference/text-openai-api
- China, models: https://platform.minimax.cn/docs/api-reference/models/openai/list-models

`platform.minimaxi.com` now 302-redirects to `platform.minimax.cn`.

1. **Base URLs:**
   - International: OpenAI-compatible `https://api.minimax.io/v1`; native `POST https://api.minimax.io/v1/text/chatcompletion_v2`; Anthropic-compatible `https://api.minimax.io/anthropic`.
   - China: OpenAI-compatible **`https://api.minimax.cn/v1`**, and the China models spec lists the server `https://api.minimax.cn`.
   - The old China host `api.minimaxi.com` does not appear on the current pages. Whether it still works is **UNVERIFIED**.
   - The China Anthropic-compatible path is **UNVERIFIED**; it is presumably `https://api.minimax.cn/anthropic`.
2. **Auth:** `Authorization: Bearer <key>`. The OpenAPI spec labels it "JWT", but the value is the API key. The Anthropic-compatible models endpoint uses `x-api-key`.
3. **Chat:** use the OpenAI-compatible `POST /v1/chat/completions` (**preferred**). Deviations:
   - `temperature`, `top_p`, `presence_penalty`, `frequency_penalty` and `logit_bias` "will be ignored". The native page instead gives ranges, for example temperature in (0, 1]; the pages conflict.
   - `n` must be 1, and `function_call` is not supported (use `tools`).
   - `max_tokens` is legacy and thinking tokens count toward it, so a low value can return `finish_reason: "length"` with **empty content**. Use `max_completion_tokens`.
   - `reasoning_split: true` puts thinking in `reasoning_content`. Otherwise thinking stays inline in `content` as `<think>…</think>`.
   - Some models reject `thinking: {type: "disabled"}` and `reasoning_effort: "none"` with a 400.
   - The native endpoint adds `base_resp` and `*_sensitive` fields, and its stream ends with an object of type `chat.completion` rather than a `[DONE]` line.
4. **Models:** `GET /v1/models` (OpenAI shape) returns `{object:"list", data:[{id, object:"model", created, owned_by}]}`. `GET /anthropic/v1/models` (Anthropic shape) is also available.
5. **Streaming:**
   - With the OpenAI-compatible endpoint, `stream_options.include_usage: true` includes usage in the stream. The SSE framing and the `[DONE]` line are not shown in the docs, so they are **UNVERIFIED** and presumably follow OpenAI.
   - The native endpoint streams `chat.completion.chunk` objects, and the last item is a full `chat.completion` holding `usage` and `base_resp`.
6. **JSON and tools:**
   - Function `tools` are supported; the native `tool_choice` accepts only `auto`.
   - `response_format` is **not mentioned** on the OpenAI-compatible page. The native page documents `json_schema` but says it is "only supported by `MiniMax-Text-01`", a model missing from the current model enum. Treat JSON mode as **unsupported or UNVERIFIED**, and validate JSON on the client.
7. **Usage fields:** the native schema documents only `total_tokens`. The examples also show `prompt_tokens`, `completion_tokens`, `total_characters` and `completion_tokens_details.reasoning_tokens`.
8. **Errors:** errors use `base_resp.status_code` and `status_msg`, at least on the native endpoint. **Which HTTP status they arrive with, and whether the OpenAI-compatible endpoint returns `{"error":{...}}` instead, is UNVERIFIED.** The adapter should check both the HTTP status and `base_resp`.
   - **Rate limit:**
     - `1002` "rate limit".
     - `1039` "token limit".
     - `1041` "conn limit".
     - `1045` concurrency.
     - `2045`, `2046`, `2047`: growth limits.
     - `2062`: M Plan rate limit.
     - `2064`: cluster under high load.
   - **Balance or quota:**
     - `1008` "insufficient balance".
     - `2053` "insufficient credit".
     - `2056` "usage limit exceeded".
     - `2067`: usage limit reached and credit auto-consumption is off.
   - Authentication: `1004` and `2049` (invalid API key).
   - Model problems: `2022` the model does not exist; `2061` and `2068` the plan does not cover the model; `2069` the model is no longer available.
9. **Deprecations:** in the native API, `max_tokens` is deprecated in favour of `max_completion_tokens`.

## 8. Ollama local (`ollama_local`)

Sources:
- API intro: https://docs.ollama.com/api/introduction
- Chat: https://docs.ollama.com/api/chat
- Tags: https://docs.ollama.com/api/tags
- Show model details: https://docs.ollama.com/api-reference/show-model-details
- Version: https://docs.ollama.com/api-reference/get-version
- OpenAI compatibility: https://docs.ollama.com/api/openai-compatibility
- Streaming: https://docs.ollama.com/api/streaming
- Errors: https://docs.ollama.com/api/errors

1. **Base URLs:**
   - Local: native `http://localhost:11434/api` and OpenAI-compatible `http://localhost:11434/v1`.
   - Cloud: `https://ollama.com/api` and `https://ollama.com/v1`.
   - An Anthropic client can point at `http://localhost:11434`, and the client appends `/v1/messages`.
   - NFactory gotcha: use `127.0.0.1`, not `localhost`. From inside Docker, the host is reached through `host.docker.internal`.
2. **Auth:** none locally; the OpenAI SDK needs some key value, and Ollama ignores it. Ollama Cloud uses `Authorization: Bearer <OLLAMA_API_KEY>`.
3. **Chat:**
   - Native `POST /api/chat`: `model`, `messages` (with `images` and `tool_calls`), `tools`, `format` (`"json"` or a JSON-schema object), `options` (`temperature`, `num_ctx`, `num_predict`, `stop`, …), `stream` (**default true**), `think`, `keep_alive`.
   - OpenAI-compatible `/v1/chat/completions`. Supported: `response_format`, `tools`, `stream_options.include_usage`, `reasoning_effort`, among others. **Not supported:** `tool_choice`, `logit_bias`, `user`, `n`, logprobs.
   - **The context size (`num_ctx`) cannot be set through the OpenAI API**; it needs a Modelfile.
4. **Models:**
   - Native `GET /api/tags` returns `{models:[{name, model, modified_at, size, digest, details:{format, family, families, parameter_size, quantization_level}, remote_model?, remote_host?}]}`.
   - `POST /api/show {model}` returns `capabilities[]` (for example `completion`, `tools`, `thinking`, `vision`) and `model_info["<arch>.context_length"]`.
   - `GET /api/version` returns `{version}`, which works as a health check.
   - The OpenAI-compatible `GET /v1/models` also exists.
5. **Streaming:**
   - Native endpoints return **NDJSON** (`application/x-ndjson`), not SSE: one JSON object per line, and the last one has `done: true` and `done_reason`.
   - The OpenAI-compatible endpoints return SSE. A `[DONE]` line is assumed, as in OpenAI, but the docs do not show one (**UNVERIFIED**).
6. **JSON and tools:**
   - Native `format` accepts `"json"` or a full JSON schema, which enforces structured output.
   - On the OpenAI-compatible side `response_format` is listed as supported, but the docs do not say whether both `json_object` and `json_schema` work (**UNVERIFIED** for `json_schema`).
   - Tools work in both APIs. Whether a model supports tools depends on the model: check `capabilities` from `/api/show`.
7. **Usage fields:**
   - Native: `prompt_eval_count`, `prompt_eval_cached_count` and `eval_count`, plus durations in ns (`total_duration`, `load_duration`, `prompt_eval_duration`, `eval_duration`).
   - OpenAI-compatible: the usual `usage` object (the exact fields are **UNVERIFIED**).
8. **Errors:** `{"error":"<string>"}`, with status 400, 404 (unknown model), 429, 500 or 502 (cloud model unreachable).
   - Mid-stream errors arrive as an NDJSON object with `error`, and the HTTP status stays 200.
   - There is no quota concept locally. A 429 is only possible with cloud models.
9. **Which to prefer:** the docs make no recommendation. **The native `/api/*` endpoints are recommended for NFactory**, for four reasons:
   - `/api/tags` and `/api/show` give real discovery, including capabilities and context length.
   - `num_ctx` and `keep_alive` can be set per request.
   - `format` takes a JSON schema.
   - Errors are explicit.

   The `/v1` OpenAI-compatible layer is a valid fallback that reuses the OpenAI-compatible adapter. The API is unversioned and announces deprecations in release notes.

---

## Summary

| id | base URL(s) | auth | OpenAI-compatible? | models endpoint | JSON mode | tools | rate-limit vs quota signal |
|---|---|---|---|---|---|---|---|
| `openai_api` | `https://api.openai.com/v1` | `Authorization: Bearer` | native (Chat Completions; Responses recommended) | `GET /models` | `json_object`, `json_schema` (strict) | function + custom; `tool_choice` none/auto/required/named | both 429; quota = `error.code` in {`credit_balance_exhausted`, `*_spend_limit_exceeded`, `organization_usage_limit_exceeded`} (`type` may be `insufficient_quota`); rate = rate-limit / `slow_down` + `Retry-After` |
| `anthropic_api` | `https://api.anthropic.com` (`/v1/messages`) | `Authorization: Bearer` (or legacy `x-api-key`) + `anthropic-version: 2026-10-21` or `2023-06-01` | **no** (Messages API) | `GET /v1/models` (with capabilities and lifecycle) | `output_config.format` json_schema | yes; `strict`; forced choice refused on some models | rate = 429 `rate_limit_error` + `retry-after`; tier spend cap = 429 with no `retry-after` + `details.error_code=enforced_spend_limit_reached`; user spend limit = 400; billing = 402; overload = 529 |
| `deepseek_api` | `https://api.deepseek.com` (+ `/beta`, `/anthropic`) | `Authorization: Bearer` | yes (penalties ignored, thinking params) | `GET /models` | `json_object` only | function (strict = beta) | rate/concurrency = 429; balance = **402** |
| `zai_glm_api` | intl `https://api.z.ai/api/paas/v4`; CN `https://open.bigmodel.cn/api/paas/v4`; Coding Plan `…/api/coding/paas/v4` | `Authorization: Bearer` | yes in practice (`tool_choice` auto only, 1 stop word) | **none documented** | `json_object` only | function, retrieval, web_search; auto only | all 429; switch on `error.code`: rate `1302`/`1305`; quota `1113`, `1308`–`1321` |
| `moonshot_kimi_api` | intl `https://api.moonshot.ai/v1`; CN `https://api.moonshot.cn/v1` (keys not interchangeable) | `Authorization: Bearer` | yes in practice | `GET /v1/models` (+ capability flags) | `json_object`, `json_schema` | function; auto/none/required/named | all 429; `error.type`: rate `rate_limit_reached_error`; quota `exceeded_current_quota_error`; overload `engine_overloaded_error` |
| `qwen_api` | `https://{WorkspaceId}.{cn-beijing \| ap-southeast-1 \| us-east-1 \| eu-central-1 \| ap-northeast-1 \| cn-hongkong}.maas.aliyuncs.com/compatible-mode/v1` (legacy `dashscope[-intl].aliyuncs.com`) | `Authorization: Bearer` (region-bound key) | yes (`enable_thinking` top-level; no `required` tool_choice on Qwen) | **none documented** (UNVERIFIED) | `json_object`, `json_schema` | function | rate = 429 `Throttling*` (**`insufficient_quota` here means TPM rate limit**); balance = 400 `Arrearage`, 429 `*BillOverdue`, 403 `AllocationQuota.FreeTierOnly` |
| `minimax_api` | intl `https://api.minimax.io/v1`; CN `https://api.minimax.cn/v1`; native `/v1/text/chatcompletion_v2`; Anthropic `/anthropic` | `Authorization: Bearer` | yes (sampling params ignored, `n`=1) | `GET /v1/models` | not documented on OpenAI-compatible (UNVERIFIED) | function; auto | `base_resp.status_code`: rate `1002`/`1039`/`1041`/`2045`–`2047`; balance `1008`/`2053`/`2056`/`2067` (HTTP status UNVERIFIED) |
| `ollama_local` | `http://127.0.0.1:11434/api` (native, preferred), `/v1` (OpenAI) | none locally (Bearer for cloud) | `/v1` yes (no `tool_choice`, no `num_ctx`) | `GET /api/tags` (+ `POST /api/show`), `GET /v1/models` | native `format` = `json` or schema; `/v1` `response_format` | yes, depending on the model | no quota locally; 429 only for cloud; mid-stream error = NDJSON `{"error"}` with status 200 |

## Implications for the adapters

- **Classify quota errors per provider. A generic "429 means retry" rule is wrong for every provider listed here.**
  - OpenAI, Z.ai, Kimi and Qwen all put quota problems behind 429.
  - Anthropic and DeepSeek use 402 for billing or balance.
  - Qwen's `insufficient_quota` is a TPM rate limit.
  - MiniMax signals both rate limits and balance through `base_resp.status_code`.
- **Stream parsers** must skip SSE comments (DeepSeek's `: keep-alive`) and blank lines. They must accept usage in either place: on the last content chunk (DeepSeek, Z.ai) or on a separate `choices: []` chunk (OpenAI, Kimi, Qwen). Anthropic uses named events and no `[DONE]`. Ollama native uses NDJSON.
- **Do not send `stream_options`** to Z.ai (not documented), and send it to DeepSeek only together with `stream: true`.
- **JSON output:** only OpenAI, Anthropic, Kimi, Qwen and Ollama native enforce a schema. DeepSeek and Z.ai offer `json_object` only, and MiniMax's support is unclear. NFactory already validates agent output with Pydantic, so keep that validation for every provider.
- **Region and workspace config:** Z.ai (intl or CN, general or Coding Plan), Kimi (intl or CN, separate keys), Qwen (six regions plus a workspace subdomain, region-bound keys) and MiniMax (intl or CN) need a region selector or an admin-editable base URL. A single default host will not cover them.
- **Discovery gaps:** Z.ai and Qwen have no documented model listing, so they need the admin catalog.

## Embeddings (phase 3, ADR-0007)

Checked on 2026-11-02. Only these two APIs are offered as embedding engines; the others are not proposed until their official docs are verified.

| Provider | Endpoint | Request | Response | Limits |
|---|---|---|---|---|
| OpenAI (and the custom OpenAI-compatible endpoint) | `POST {base}/embeddings` | `model`, `input` (string or array of strings), optional `encoding_format` (`float` or `base64`), `dimensions` (text-embedding-3 and later) | `{"object": "list", "data": [{"object": "embedding", "index", "embedding": [...]}], "model", "usage": {"prompt_tokens", "total_tokens"}}` | input never empty; at most 2048 inputs per request; 8192 tokens per input; 300,000 tokens per request |
| Ollama | `POST /api/embed` | `model`, `input` (string or array), optional `truncate` (default `true`), `dimensions`, `keep_alive`, `options` | `{"model", "embeddings": [[...]], "total_duration", "load_duration", "prompt_eval_count"}` | `truncate: false` turns over-long inputs into an error |

Sources: https://developers.openai.com/api/reference/resources/embeddings/methods/create (via Context7; the platform.openai.com page refuses automated reads) and https://docs.ollama.com/api/embed.

NFactory sends `encoding_format: "float"`, batches of 64 chunks of at most 1500 characters, and orders OpenAI vectors by `index`. A reply with the wrong number of vectors is an `invalid_response`.
