# 07 — Frontend Specification

## 1. Purpose & scope

A single-page chat interface. No auth, no routing complexity beyond the one screen (a secondary "About/data" panel may be a modal/drawer rather than a separate route). Must load fast, work on mobile, and make the system's grounded/sourced nature visible rather than hidden — this is a trust-building product, not a generic chat clone.

## 2. Required screen elements

1. **Header** — product name ("EstateBot" or chosen name), one-line description ("Ask about DarGlobal & Wasalt properties"), and an "About this data" affordance (icon/button opening a panel — see §4).
2. **Chat log** — scrollable, auto-scrolls to newest message, clearly distinguishes user vs. assistant messages (avatar/alignment/color), renders assistant markdown (bold, lists, links) safely (sanitized, no raw HTML injection — see §7).
3. **Citation chips** — under any assistant message that has `citations`, render small clickable chips (e.g. "DG1 ↗", "Trump Cliff Villas ↗") that open the source URL in a new tab (`target="_blank" rel="noopener noreferrer"`) and/or open the `/api/listings/{source_site}/{source_id}` debug view in a lightweight modal.
4. **Composer** — text input + send button; `Enter` sends, `Shift+Enter` (or equivalent) inserts newline; disabled while a response is streaming in, with a visible "stop generating" affordance if streaming is implemented (nice-to-have, not mandatory).
5. **Suggested prompts** — on first load (empty conversation), show 4–6 clickable example questions drawn from `docs/01-SPEC.md` §4 use cases, tailored to the actual scraped corpus (don't suggest a question the corpus can't answer) — this materially improves first-impression review quality since the reviewer doesn't have to guess what to ask.
6. **Typing/loading indicator** — shown between send and first token/full response.
7. **Error state** — shown inline in the chat log as a distinct message style (not a silent failure or browser alert) when `/api/chat` errors or the client-side timeout (§6) fires; includes a retry action.
8. **Free-model selector** — an accessible custom menu integrated into the composer, populated from `/api/models`. It presents each model's plain-language purpose, free status, and selected state without exposing raw provider IDs. “Auto” is the default; a chosen model is persisted for the browser session and tried first without disabling fallback. The trigger/menu use the appropriate expanded, menu, and radio-item semantics and support arrow, Home, End, Enter, and Escape keyboard interaction.
9. **Actual-model disclosure** — model-backed assistant messages display the provider-returned `model_used`, including when fallback served a different model than the user selected.
8. **Rate-limit state** — when a `429` is received, show the countdown from `Retry-After` and disable the composer until it elapses.

## 3. States to explicitly design for

| State | UI behaviour |
|---|---|
| Empty conversation (first load) | Header + suggested prompts + empty composer, no chat log clutter. |
| Message sent, awaiting response | User message appended immediately (optimistic render); typing indicator shown; composer disabled. |
| Streaming response | Tokens append progressively to a growing assistant bubble; citations render once the `done` event arrives. |
| Non-streaming fallback | If streaming isn't supported/enabled, show typing indicator until the full response arrives, then render at once. |
| Grounded answer | Normal rendering with citation chips. |
| "Not found in our data" answer (`grounded: false`) | Rendered distinctly (e.g. a subtle icon/label "no matching data found") so the user understands this is an honest gap, not a bug — reinforces the groundedness value prop rather than reading as a broken bot. |
| Network/timeout error | Distinct error bubble: "Something went wrong reaching EstateBot. [Retry]" — never a blank screen or unhandled console-only error. |
| Rate limited | Distinct bubble with countdown; composer disabled until countdown ends. |
| Backend cold-start (if hosting tier sleeps) | If `/api/health` is slow/unreachable on first load, show a "Waking up the server, this can take up to ~30s on the free tier" banner rather than a blank/broken page — set this expectation explicitly if the chosen host has this behaviour (see `docs/08-DEPLOYMENT.md`). |
| Long conversation | Chat log scroll performance remains smooth at 50+ messages (virtualize if needed — unlikely to be necessary at assignment scale, but don't let the DOM grow unbounded without at least basic sanity). |

## 4. "About this data" panel content (mandatory — see `docs/05-CHATBOT-RAG-SPEC.md` §8)

- Plain-language explanation: "EstateBot answers using data scraped from the public DarGlobal and Wasalt websites. It is an independent project, not affiliated with or endorsed by either company."
- Live stats pulled from `GET /api/stats`: total listings, sources, cities covered, last scrape timestamp (formatted human-readable, e.g. "Data last updated Aug 30, 2026").
- The number of curated free models; the active preference remains continuously visible in the composer, and each model-backed answer discloses the actual model that served it.
- A short disclaimer: prices/availability may be out of date; verify directly with the source before making decisions.
- A link (or the two source domain names as plain text, not necessarily hyperlinked if that raises concerns about implying endorsement — hyperlinking to the public homepage is fine and standard attribution practice) to DarGlobal and Wasalt.

## 5. Visual/UX requirements

- Fully responsive: usable on a 360px-wide mobile viewport up to desktop widths; composer and chat log must remain usable without horizontal scrolling at any width.
- Sufficient color contrast (WCAG AA minimum) for all text, including citation chips and the "not found" state styling.
- `prefers-reduced-motion` respected (no forced animation on the typing indicator/token streaming if the user has this preference set).
- No layout shift when citation chips or the "About" panel load.
- Visually communicate "this is grounded/sourced," e.g. a small "Sources" label above citation chips, distinct from generic chat-bubble styling — this is a differentiator worth making visually obvious to a reviewer skimming quickly.
- Keep the composer compact before typing and fixed within reach without obscuring the latest message. The model choice belongs in its toolbar rather than in a separate settings form.
- Use a restrained product hierarchy: compact identity/status header, one clear empty-state question, structured prompt cards, readable answer typography, and citations as secondary evidence cards.

## 6. Client-side resilience

- Client-side request timeout (e.g. 50s, slightly above the backend's 45s hard ceiling from `docs/05-CHATBOT-RAG-SPEC.md` §6) so the UI never appears to hang forever even if something bypasses the backend's own timeout handling.
- Retry affordance on failed sends (does not auto-retry silently/repeatedly — user-initiated retry only, to avoid compounding rate-limit or cost issues).
- Conversation state persisted in `sessionStorage` (not `localStorage`, to avoid indefinite persistence of chat content across sessions) keyed by `conversation_id`, so an accidental refresh doesn't lose the visible transcript (the server already has the authoritative history — this is purely for UI continuity).

## 7. Security requirements (frontend side)

- Assistant markdown rendered through a sanitizing markdown renderer (e.g. a library that strips raw HTML/script tags) — never `dangerouslySetInnerHTML`/`innerHTML` with unsanitized model output, since model output is technically influenceable by scraped page content and must be treated as untrusted for rendering purposes, mirroring the backend's treatment of it as untrusted for prompting purposes (`docs/05-CHATBOT-RAG-SPEC.md` §7).
- All external links (`source_url` citations) use `rel="noopener noreferrer"`.
- No secrets/API keys in frontend bundle or source (the frontend never talks to OpenRouter directly — always via the backend).

## 8. Build/tech notes

- If a React+Vite SPA is used: TypeScript, a small state layer (React state/context is sufficient at this scope — no need for a heavy state library), a lightweight fetch/SSE client (native `EventSource` or `fetch` with a readable-stream reader, since the API uses SSE).
- If a minimal server-rendered + vanilla-JS approach is used instead (acceptable per `docs/02-ARCHITECTURE.md` §3): the same functional requirements in §2–§7 still apply in full; "minimal tech" does not mean "minimal requirements."
- Whichever is chosen, the production build must be static, cacheable assets (or trivially served), so the container/host cost is negligible.
