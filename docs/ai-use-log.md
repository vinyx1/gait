# How AI was used in Gait, and how it was checked

This project was built during CIVIC Hack 2026 (after the 7 pm hacking start on Nov 12, 2026) with AI assistance. This log is for the judges and for the team's own review.

## 1. AI used to write the code
- **Claude Code** (Anthropic) wrote most of the Python, templates and tests in this repository, working from requirements discussed with the team.
- **Human responsibility:** the team reads, runs and can explain each module. Every module has tests. Replace this line with what you personally reviewed: ______

## 2. AI used inside the product (runtime)
| Feature | Model | What it may do | What software enforces |
|---|---|---|---|
| Plain-language rewrite (`rewrite.py`) | claude-opus-5-5 | Rewrite one official passage into 2 to 6 short sentences, each with an exact supporting quote | Quote must be in the source; numbers must be in the source; no stronger wording than the quote; failures are dropped and stored with the reason |
| Access-audit agents (`agents.py`) | claude-opus-5-5 | Call five local tools about one place and one rider, then report findings with exact cited tool text | Quote in tool result; numbers in cited results; banned absolute words; agents cannot label a barrier |
| Consolidator (`agents.consolidate`) | claude-opus-5-5 | Return groups of duplicate findings only | Output must be a valid partition; no new text |

Server-side refusal fallback was enabled on the API calls. Generation is run offline by scripts and stored in `data/`; the web app does not call an AI model.

## 2b. What AI is not used for
Decision wording, recommendations, dates, votes, statuses, wards and every number in the rider tables are copied or computed by fixed code from official data.

## 3. Verification performed
- Automated tests (see `docs/architecture.md` section 5).
- Spot review of AI output by the team: tick when done.
  - [ ] Read all rewritten sentences for the demo items and compared with the official text.
  - [ ] Read the audit findings for the demo locations and checked at least five against the raw stop data.
  - [ ] Confirmed the Dundas report date problem is flagged on the page.
- Known weaknesses found and fixed during the build:
  - The model turned "request" into "will" and "must report back": added the strong-wording check.
  - The model labelled a disused bus bay a "barrier": agents can no longer assign that label.
  - The trip accessibility flag was first read as a single percentage, which confused "no information" with "not accessible": now all three values are shown.
  - The same facts appeared in three agents' words: added the grouping step.
  - A source report contains an impossible date: documented in `data/notes/`.

## 4. Data and external tools
All inputs are public, open or organizer-provided. The key for the AI service is stored in a gitignored `.env` file. No personal data was used; names of people who wrote to Council are not stored.

## 5. Other credits
FastAPI, Jinja2, pypdf, the Anthropic Python SDK, City of Toronto Open Data (Open Government Licence – Toronto), TTC GTFS, Claude Code.
