# OpenRouter Free-Model Research and Selector Decision

**Catalogue checked:** 2026-09-02  
**Source:** OpenRouter `GET /api/v1/models`  
**Scope:** zero-cost models suitable for EstateBot's grounded text-generation contract

## Findings

The live catalogue returned 21 entries whose prompt and completion prices were both zero. Two were Lyria music-generation previews with separate song pricing and audio output, so they are not free text-chat choices. The remaining catalogue included 18 `:free` variants plus the `openrouter/free` router.

Free availability is not equivalent to suitability. The catalogue also contains moderation-only, coding-focused, finance-specialized, multimodal perception, harness-restricted, very small, and reasoning-heavy models. Exposing every zero-token-price row would make the UI misleading and would increase invalid or low-quality grounded answers.

OpenRouter documents that:

- `:free` selects a zero-cost variant but can have lower rate limits and variable availability: <https://openrouter.ai/docs/guides/routing/model-variants/free>
- Specific free models can be selected directly; `openrouter/free` instead chooses a random eligible free model: <https://openrouter.ai/docs/guides/routing/routers/free-router>
- Model IDs, pricing, modalities, context, and supported parameters are discoverable from the Models API: <https://openrouter.ai/docs/api/api-reference/models/get-models>
- Free-model accounts generally have a shared daily request limit; the documented limit is 50 requests/day without at least $10 in purchased credits and 1,000/day after that threshold: <https://openrouter.ai/docs/faq>

## Curated UI choices

| Model | Context reported by catalogue | Why offered | Live evidence |
|---|---:|---|---|
| Dots3 Note Preview | 512K | New general-purpose text/vision model; followed the EstateBot source-marker contract. | HTTP 200 with valid `[[id:dg1]]` marker. |
| Nemotron 3 Ultra | 1M | Large general reasoning/orchestration model with substantial context. | HTTP 200 with valid source marker. |
| Nemotron 3 Super | 262K | Efficient general reasoning model and a useful alternative to Ultra. | HTTP 200 with valid source marker. |
| Gemma 4 31B | 262K | Existing primary; general instruction model with proven EstateBot behavior. | Direct success and deployed grounded QA; a later probe also observed a transient free-provider 429. |
| GLM 5.2 | 256K | Existing first fallback with proven contextual follow-up behavior. | Served a grounded deployed response; transient 429s remain possible. |
| MiniMax M3 | 1M | Existing dependable fallback with strong live availability in this assessment. | Multiple deployed and direct HTTP 200 responses. |

“Auto — recommended free fallback” remains the default. Auto uses the configured Gemma → GLM → MiniMax sequence. A manual choice is prepended to that sequence and deduplicated. This means selection expresses preference, not a promise that an oversubscribed free endpoint will serve the request.

## Not exposed and why

| Group/examples | Decision |
|---|---|
| `openrouter/free` | Not shown separately because EstateBot's Auto mode is deterministic, auditable, and reports the actual model rather than accepting a random route. |
| Lyria 3 music previews | Excluded: audio/music generation with separate per-song charges, not property text chat. |
| Nemotron Content Safety | Excluded: moderation/guardrail model, not an answer generator. |
| Poolside Laguna and Cohere North Mini Code | Excluded: coding-agent specialization is irrelevant to property Q&A. |
| Thinking Machines Inkling | Excluded after the API returned a harness-restriction error for ordinary chat-completions use. |
| Ling 3.0 Flash Fin | Excluded: finance-focused and produced no ordinary answer content in the bounded probe. |
| Liquid LFM 2.5 2.6B | Excluded: compact model produced no ordinary answer content in the bounded probe. |
| Nemotron Lightning / Nano Omni | Excluded: specialized high-throughput/perception roles and less consistent concise-answer behavior than the selected Nemotron variants. |
| Gemma 4 26B, MiniMax M2.7 | Excluded to avoid near-duplicate choices when newer/larger family options are already offered. |

## API and safety contract

- The browser receives choices from `GET /api/models`; it does not submit arbitrary catalogue IDs.
- `POST /api/chat` accepts an optional `model` ID and rejects IDs outside the server allow-list with HTTP 400.
- The chosen model is tried first. Provider failure, rate limiting, timeout, empty output, or invalid citations continue through the existing fallback and verification paths.
- The response's provider-returned `model_used` is displayed under the answer, so users can see when a fallback served it.
- The selector choice is stored only in browser `sessionStorage`. No API key or provider credential reaches the browser.
- The configured models were zero-cost at the dated catalogue check. Free status and availability can change, so this document records a snapshot rather than claiming permanence.
