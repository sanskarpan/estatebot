# Adversarial Product QA

**Run date:** 2026-09-03  
**Target:** local application and the public release using the full 248-record seed
**Purpose:** test the product as a hostile or unpredictable reviewer would, beyond nominal unit paths

## 1. Defects found and corrected

| Severity | Probe | Failure observed | Correction |
|---|---|---|---|
| High | `Give me every city and country you cover.` | Singular/every wording missed the coverage route and returned unrelated citations | Expanded deterministic coverage recognition |
| High | `Show properties under 2 million AED.` | Suffix currency was not parsed; explicit zero-match filters fell through to unrelated lexical records | Parse suffix currency and prohibit structured zero-match fallthrough |
| High | Independent topic after a location query | Every turn inherited two prior messages, allowing stale location/source constraints to leak | Only referential follow-ups inherit the immediately previous user turn |
| High | `asdf qwer 987` | An unrelated number activated unfiltered structured retrieval | Numeric parsing now requires price/budget/currency context |
| Medium | `List projects from Dargloabl.` | Source typo became an unscoped mixed-source request | Conservative fuzzy recognition for close DarGlobal/Wasalt typos |
| Medium | `List projects from dware.` | Unknown source silently became an unscoped project query | Explicit clarification/no-match route for unknown `from <source>` wording |
| Medium | `Show me villas from madeuphomes.` | The unknown-source guard only recognized generic project/property nouns, so a property-type query returned unrelated unscoped villas | Expanded unknown-source recognition across homes, houses, villas, apartments, flats, plots, and land |
| Medium | Prompt-extraction request with provider unavailable | Request fell into lexical retrieval and returned unrelated company/property facts | Deterministic refusal before retrieval/model generation |
| Medium | Model citation markers wrapped in parentheses | Marker removal left visible empty `()` | Remove empty wrapper punctuation and normalize adjacent spacing |
| Medium | Blank Enter submission | Native `required` validation produced an orange outline and browser tooltip | Removed conflicting native requirement; retained disabled Send and application guard |
| Medium | New chat with draft/transient UI | Conversation ID/messages cleared, but draft/banner/menu could remain | Reset all chat-scoped state while preserving model preference |
| Medium | Property price display | Stored display text could omit a known canonical currency | Append normalized currency when absent from display text |
| Low | Rich-result experience | Answers repeated text plus small source chips despite structured images/details being available | Added responsive inline property cards with safe image fallback |

## 2. Live local API probes

These checks hit the running FastAPI service over HTTP; they were not direct function calls.

| Area | Inputs / conditions | Result |
|---|---|---|
| Conversation | `hello`, punctuation variants, thanks | Correct unlabelled conversational responses; no citations/model call |
| Coverage | singular/plural and “every” wording | All 13 cities and 7 countries; no hardcoded Riyadh preamble |
| Source scope | DarGlobal, Wasalt, cross-source, close typo, unknown source | Correct scoping/balance or explicit clarification |
| Geography | mixed case, known cities/countries, Antarctica/Mars | Correct filtering; unknown locations never substituted unrelated records |
| Numeric | bedroom count, cheapest, missing price, suffix currency | Structured SQL path; null prices not invented; currency leakage prevented |
| Nonsense | punctuation only, emoji, random words with an unrelated number | Graceful no-match; no arbitrary records |
| Abuse | HTML/script strings, prompt extraction, unsupported developer | Escaped/no execution; deterministic refusal or corpus-boundary response |
| Validation | blank, 2,001 characters, overlong conversation ID, invalid model | Structured HTTP 400; no stack trace; invalid model not forwarded |
| Protocol | conversational SSE response | Token events followed by exactly one `done`, no `error` |
| Concurrency | 20 simultaneous mixed requests | 20/20 HTTP 200, no empty answers, no SQLite lock failures; completed in ~0.42 s locally |

The concurrent run used distinct test client addresses so it tested application/database concurrency rather than intentionally testing the request limiter.

## 3. Conversation-isolation probes

One server conversation was exercised with:

1. `Show villas in Riyadh`
2. `Show apartments in Jeddah`
3. `What about 2-bedroom homes there?`

The second turn did not inherit Riyadh. The referential third turn inherited the immediately previous Jeddah context and returned two-bedroom Jeddah records. The browser New chat action then produced an empty transcript and a fresh null conversation ID path.

## 4. Browser and rendering probes

| Probe | Observed result |
|---|---|
| Empty Enter | No message, invalid state, native tooltip, or orange outline; Send remained disabled |
| Greeting bubble | `hello` rendered on one line at 61×43 px; assistant reply had no misleading response label |
| Neutral coverage | Cities/countries displayed; hardcoded “not limited to Riyadh” text absent |
| New chat | Messages, draft, banner, and open menu cleared; suggestions returned |
| HTML injection | Literal `<img ... onerror=...>` displayed as text; zero injected image elements |
| 2,000-character unbroken input | No bubble or document horizontal overflow |
| Model menu at 375×812 | Seven options remained entirely inside the viewport |
| 51-turn mobile conversation | DOM capped at 100 messages (50 user + 50 assistant), no horizontal overflow |
| Refresh after stress | All 100 capped messages restored successfully |
| Reset after stress | Returned to empty state with no stale draft or messages |
| Rich property cards | Five cards rendered for generic villas, included DarGlobal and Wasalt, canonical details and links |
| Card images | Three usable remote images loaded; two missing/unusable images became clean placeholders; no console errors |
| Mobile property cards | Five 297 px cards fit a 375 px viewport; composer remained visible; no horizontal overflow |

## 5. Automated regression coverage added

The suite now covers:

- broad coverage phrasing and neutral response copy;
- deterministic prompt-extraction refusal;
- self-contained versus referential context inheritance;
- source typo/unknown-source behavior;
- numeric gibberish and suffix-currency parsing;
- explicit structured zero-match isolation;
- currency preservation in normalized answer chunks;
- empty-parenthesis citation cleanup;
- marker-only and cross-source ambiguous citation rejection;
- conversation ID length bounds and normalized invalid-model errors;
- blank-composer behavior, true reset hooks, property-card rendering contracts, and image fallback.

## 6. Public release validation

The released build was checked again over HTTPS and through a fresh in-app browser session:

- greeting and neutral coverage routes returned deterministic responses with no false source label;
- `Show me villas from madeuphomes` returned an explicit clarification instead of unrelated records;
- a generic villa request rendered eight responsive property cards split evenly across DarGlobal and Wasalt;
- six available remote property images loaded at their natural dimensions; cards without usable imagery retained a clean fallback;
- the model menu exposed Auto plus six free models and remained inside the mobile viewport;
- selecting Gemma 4 31B changed the request preference; when the free route was unavailable, the successful MiniMax M3 fallback was disclosed in the answer attribution;
- New chat cleared the transcript, draft, transient state, and conversation context while retaining the intentional model preference;
- the textarea had no native validation state, tooltip, or orange inner focus rectangle;
- all cards and the composer remained within the mobile viewport with no document overflow;
- CI passed the 74-test suite, Compose validation, clean image build, seeded boot, and container smoke checks for the released revisions.

Physical/timed limitations remain separate: a native screen-reader session, a deliberately severed public TCP stream, and a complete host idle-window wake have not been claimed as observed tests.
