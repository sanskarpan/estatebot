# 07 — Frontend Specification

## 1. Purpose & scope

A single-page chat interface implemented in vanilla HTML, CSS, and JavaScript and served by FastAPI. It has no authentication or client-side routing. A native About dialog provides corpus disclosure. The interface must load quickly, work on mobile, and make groundedness visible without applying a source-verification label to uncited responses.

## 2. Required screen elements

1. **Header** — product name, concise description, live corpus-record status, New chat, and About dialog controls.
2. **Chat log** — scrollable, auto-scrolls to newest message, clearly distinguishes user vs. assistant messages (avatar/alignment/color), renders assistant markdown (bold, lists, links) safely (sanitized, no raw HTML injection — see §7).
3. **Citation results** — property citations render as compact result cards using stored image, location, category, bedroom, and price metadata; missing images use a quiet placeholder. Supporting documents use compact source chips. Every item opens its canonical source in a new tab with `target="_blank" rel="noopener noreferrer"`.
4. **Composer** — auto-sizing textarea + send button; `Enter` sends and `Shift+Enter` inserts a newline. Send is disabled for blank input and while a response is pending. Blank submissions are handled by the application without invoking the browser's intrusive native validation tooltip.
5. **Suggested prompts** — on first load (empty conversation), show 4–6 clickable example questions drawn from `docs/01-SPEC.md` §4 use cases, tailored to the actual scraped corpus (don't suggest a question the corpus can't answer) — this materially improves first-impression review quality since the reviewer doesn't have to guess what to ask.
6. **Typing/loading indicator** — shown between send and first token/full response.
7. **Error state** — shown inline in the chat log as a distinct message style (not a silent failure or browser alert) when `/api/chat` errors or the client-side timeout (§6) fires; includes a retry action.
8. **Free-model selector** — an accessible custom menu integrated into the composer, populated from `/api/models`. It presents each model's plain-language purpose, free status, and selected state without exposing raw provider IDs. “Auto” is the default; a chosen model is persisted for the browser session and tried first without disabling fallback. The trigger/menu use the appropriate expanded, menu, and radio-item semantics and support arrow, Home, End, Enter, and Escape keyboard interaction.
9. **Actual-model disclosure** — model-backed assistant messages display the provider-returned `model_used`, including when fallback served a different model than the user selected.
10. **Rate-limit state** — when a `429` is received, show the countdown from `Retry-After` and disable the composer until it elapses.
11. **True reset boundary** — New chat clears the visible transcript, conversation ID, draft, banners, and open model menu while retaining the user's model preference.

## 3. States to explicitly design for

| State | UI behaviour |
|---|---|
| Empty conversation (first load) | Header + suggested prompts + empty composer, no chat log clutter. |
| Message sent, awaiting response | User message appended immediately (optimistic render); typing indicator shown; composer disabled. |
| Streaming response | Tokens append progressively to a growing assistant bubble; citations render once the `done` event arrives. |
| Non-streaming fallback | If streaming isn't supported/enabled, show typing indicator until the full response arrives, then render at once. |
| Grounded answer | Normal rendering with citation chips. |
| Conversational reply | Brief unlabelled assistant response; do not imply that a greeting was retrieved or source-verified. |
| "Not found in our data" answer (`grounded: false`) | Rendered distinctly (e.g. a subtle icon/label "no matching data found") so the user understands this is an honest gap, not a bug — reinforces the groundedness value prop rather than reading as a broken bot. |
| Network/timeout error | Distinct error bubble: "Something went wrong reaching EstateBot. [Retry]" — never a blank screen or unhandled console-only error. |
| Rate limited | Distinct bubble with countdown; composer disabled until countdown ends. |
| Backend cold-start (if hosting tier sleeps) | If `/api/health` is slow/unreachable on first load, show a "Waking up the server, this can take up to ~30s on the free tier" banner rather than a blank/broken page — set this expectation explicitly if the chosen host has this behaviour (see `docs/08-DEPLOYMENT.md`). |
| Long conversation | Chat log scroll performance remains smooth at 50+ messages (virtualize if needed — unlikely to be necessary at assignment scale, but don't let the DOM grow unbounded without at least basic sanity). |

## 4. About dialog content

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
- Response-state labels must be literal: show the serving model for model-backed output, “Source-grounded” only when citations exist, “Corpus summary” for deterministic corpus summaries, and “No matching source data” for honest gaps. Never display a generic “verified” label on an uncited or empty result.
- Keep the composer compact before typing and fixed within reach without obscuring the latest message. The model choice belongs in its toolbar rather than in a separate settings form.
- Use a restrained product hierarchy: compact identity/status header, one clear empty-state question, structured prompt cards, readable answer typography, and citations as secondary evidence cards.
- Present the empty state as a property-research workspace, including compact live signals for indexed records, data sources, and available AI routes; these are functional orientation, not decorative vanity metrics.
- Use one consistent inline-SVG icon language for controls, model routing, data status, source labels, property placeholders, and external links. Do not rely on emoji or font glyphs for interface icons.
- Typography uses a modern system sans-serif stack with a dense editorial display treatment, restrained green emphasis, subtle data-grid depth, and accessible green focus rings.

## 6. Client-side resilience

- Client-side request timeout (50s, slightly above the backend's 45s model-chain ceiling from `docs/05-CHATBOT-RAG-SPEC.md` §5) so the UI never appears to hang forever.
- Retry affordance on failed sends (does not auto-retry silently/repeatedly — user-initiated retry only, to avoid compounding rate-limit or cost issues).
- Conversation state persisted in `sessionStorage` (not `localStorage`, to avoid indefinite persistence of chat content across sessions) keyed by `conversation_id`, so an accidental refresh doesn't lose the visible transcript (the server already has the authoritative history — this is purely for UI continuity).

## 7. Security requirements (frontend side)

- Assistant text is HTML-escaped first, then a deliberately small markdown subset is applied. Raw model/user HTML is never inserted as executable markup; this mirrors the prompt boundary in `docs/05-CHATBOT-RAG-SPEC.md` §4.
- All external links (`source_url` citations) use `rel="noopener noreferrer"`.
- No secrets/API keys in frontend bundle or source (the frontend never talks to OpenRouter directly — always via the backend).

## 8. Build/tech notes

- The implemented client uses static vanilla assets and native `fetch` with a readable-stream parser for SSE.
- All user/model strings are escaped before the small supported markdown subset is rendered.
- The transcript is capped at 100 visible messages and persisted in `sessionStorage`; server prompt history is bounded independently.
- Static assets are served by the same FastAPI process, eliminating split-origin runtime complexity.
