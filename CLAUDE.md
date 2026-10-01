# Alta Via 8 – 2027 Booking Monitor

## Purpose
Backup plan to AV1 (23 Jun – 1 Jul 2027). Watch AV8 hut booking pages for 23–30 Jun 2027 and alert Justin on Telegram when something is actionable.

Trip defaults (never change without asking): **2 guests, dorm/bunk beds only, half board preferred**, all stays 1 night. Where a hut has no half board, prefer a nearby half-board hut and keep the original as backup.

## Setup
- GitHub repo `av8-monitor` (public), GitHub Actions, new Telegram bot (separate from AV1).
- Trigger: cron-job.org hourly at :05 (main) + GitHub cron `17 * * * *` (backup).
- Files: `monitor.py`, `huts.json` (hut config), `reminders.json`, `state/` (committed each run), `STATUS.md`.

## Hut list (trip night = check-in)
| Night | Hut | Role | Booking | Meals | 2027 info |
|---|---|---|---|---|---|
| 23 Jun | Plose | preferred | RoomRaccoon online | Half board | Not stated |
| 24 Jun | Genova (Schlüterhütte) | preferred | Email/phone, €20 pp deposit | B&B, dinner à la carte for guests | Not stated |
| 25 Jun | Resciesa | preferred | Email only | Dinner à la carte | Not stated |
| 26 Jun | Ortisei | not monitored | Hotels bookable now | — | — |
| 27 Jun | Firenze | preferred | RoomRaccoon online | B&B; HB only groups 10+ | From Feb 2027 (hut site only) |
| 28 Jun | Sasso Piatto | preferred | Email (official site) | Half board (reviews) | Not stated |
| 29 Jun | Molignon | preferred | Online (seiseralm.it) | Check | Not stated |
| 30 Jun | Tierser Alpl | preferred (HB) | Online | HB from €97 | Not stated |
| 30 Jun | Schlernhaus | backup | Request form (JS) | B&B, dinner extra | Season 8 Jun – 10 Oct 2027 |

No half-board alternatives found near Genova, Resciesa or Firenze (Juac and Brogles are also B&B in summer; Brogles opens late June/July).

## Check types
- `engine` (Plose, Firenze): fetch RoomRaccoon page for the trip night via r.jina.ai, save `state/debug/<id>.txt`, classify rooms/none/unclear. URL date params are UNVERIFIED; confirm on first run.
- `page` (others): extract booking-related sentences, fingerprint, alert on new 2027/"open" text.
- Fetch fallback: requests → curl_cffi browser → r.jina.ai reader.

## Rules
- Never book, submit forms, send emails or pay without explicit approval. Justin chose page watch only (no enquiry emails) for email-only huts.
- A blank or unclear result is "not live yet / unknown", never "sold out".
- Cross-check facts with a second source before reporting. Single-source: Firenze Feb 2027.
- Keep answers brief; use tables. Show times in KL first, Italy second.
