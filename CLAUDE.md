# CLAUDE.md: guide for AI assistants working on this repository

Read this whole file before changing anything. It records what the project is, the rules it must follow, how to run it, and the mistakes already made so they are not repeated.

## 1. What this project is

**TripLens** (working name; the owner may rename it) is a web app built for **CIVIC Hack 2026** (Future Cities Institute, University of Waterloo), **Challenge 1: "Making municipal decisions easier to understand"**. The brief asks for a working proof of concept that helps residents understand a proposed municipal decision, how it could affect them, and when they can have a say. A municipal leader should be able to use it without the team present.

One-sentence pitch: *Council decisions in plain language, with every claim checked against its source, and a view of how the same decision lands on different riders (a wheelchair user, a senior with a cane or walker, a shift worker).*

The owner is **Vince** (University of Waterloo student). Work is for a hackathon; the audience for the code and docs is the judges as well as Vince.

### What it does
1. **Explain layer** (`/` and `/item/<id>`): for a City of Toronto council or committee item it shows where it stands, the staff recommendation next to the decision, wards, whether the official page shows "Request to Speak" / "Submit Comments" buttons, the process timeline, exact quotes from linked reports with page numbers, and AI-written plain-language sentences that passed software checks.
2. **Rider access view** (`/access/<location>?persona=...`): for places linked to an item, compares transit access for three riders using open data, plus checked findings written by AI agents.
3. **Route check** (`/route`): a resident enters a start address, a destination, the route(s) they take and the stops they use, a rider, a day and a time. The tool lists what the open data shows along that trip: decisions near it, works along it, how the stops work for that rider, and decisions that name their route.

4. **Before and after a change** (on the route result page): a municipal change is stored as structured effects (remove stops, remove shelters or benches) in `data/changes/*.json`, each with exact quotes from saved source text. `triplens/changes.py` applies the change to the resident's trip (a removed stop moves them to the nearest remaining stop in their direction) and reruns the rider rules on both versions, then lists new accessibility issues. Real example: the TTC proposal to remove nine 512 St Clair stops (`/route/example/stclair-512`). Simulated example, labelled everywhere: shelter and bench removal at two 501 Queen stops.

5. **3D map** (`/map`): MapLibre with OpenFreeMap tiles, tilted 3D buildings. Click start and destination, choose a route from those with stops within 800 m of both (listed by number, not ranked), click your boarding and exit stops, then see walking legs on the City pedestrian network, shelters (blue boxes) and benches (brown) in 3D, removed stops (red rings), and before (blue) vs after (orange) with a toggle. Privacy note: map tiles come from OpenFreeMap, which sees the area viewed; clicked points go only to the local server. JSON endpoints: `/api/routes_near`, `/api/route_stops`, `/api/trip`.
6. **Walking on real sidewalks:** `triplens/walk.py` routes walks on the City Pedestrian Network (data/geo/pednet.csv to pednet_graph.pkl, both gitignored); wheelchair and walker riders avoid no-sidewalk segments; flags no-sidewalk metres and unsignalled crossings. Falls back to straight line times 1.3 when no path is found.

7. **Research agent for past decisions** (`triplens/research.py`, `scripts/run_research.py`, page `/research/<route>`): Claude with three tools (search the Voting Record and Report Request Log stored in `data/records/`, list documents of saved item pages, read passages from City legdocs PDFs) finds decisions that changed a route. Findings are kept only if the quote is on the cited page. A person turns findings into a change file. Found: RapidTO (item 2025.EX25.4, July 2025) removed 7 Bathurst stops at Dewbourne, Ardmore and Heathdale, and the 29 Dufferin stop at Croatia.
8. **Past (implemented) changes:** change files with `"phase": "implemented"` and `restore_removed_stops` effects. The current schedule is "after"; "before" puts the removed stops back where the cross street meets the route line (`changes._reconstruct`, labelled "location reconstructed", shelter and bench unknown). Demo: `/route/example/bathurst-7-past` and the map sample "7 Bathurst" (senior with a walker at 1599 Bathurst St: about 62 m before, about 419 m today).

### What it does NOT do (do not add without being asked)
- It does **not** plan trips, time trips, or suggest routes, stops or alternatives. Before/after works only for changes entered as structured effects; it does not read schedules of proposed networks (none are published). The resident supplies their route and picks their own stops. (A "shortest walk" stop suggestion was added once without being asked and had to be removed.)
- It does **not** recommend, take sides, or say a trip is possible or safe. The brief requires neutral, non-partisan communication.
- It does **not** store anything about a user. No accounts, cookies, analytics, or logs of addresses.

## 2. Hard constraints (hackathon)

| Item | Rule |
|---|---|
| Deadline | Hacking ends **10:00 am Saturday Nov 14, 2026 (ET)**. Everything is due on Devpost by then. **No code or submission edits after.** |
| Deliverables (all four) | (1) code repo link (commits are checked), (2) 2 to 3 minute demo video (over 3 minutes is not considered), (3) one-page Municipal Readiness Report on the organizers' Word template, saved as PDF, (4) short Devpost description |
| Scoring (100) | Project 40 (functionality only 15), Software design and code understanding 20 (requirements and UML, architecture rationale, code awareness, references), Presentation 40 (readiness report 20, video 20) |
| AI use | Disclose it. Judges mark down generated code the team cannot explain or modify. The top references band needs documented AI use and how it was verified (`docs/ai-use-log.md`). |
| Data | Public, open or organizer-provided data only. No personal or confidential information. |
| Team | 1 to 4 people, at least one currently enrolled Waterloo student |
| Originality | Nothing brought in pre-built. Work started after launch (7 pm Nov 12). |

Priorities follow the scoring: finished deliverables and explainable, tested code beat extra features. Do not start new features late in the schedule without being asked.

## 3. How to work with Vince

- **Consult on design before building.** Propose the design (modules, data, trade-offs), get a decision, then build. Ask short, plain questions. Do not assume Vince knows jargon; explain terms with a concrete example.
- **Do not add features nobody asked for.** If a convenience seems useful, mention it and let Vince decide. Do not describe the product as doing something it does not do.
- **Say what is not built.** Be explicit about stubs, simulations and limits. A claim the demo cannot back up costs more than a gap.
- **Explain code on request** so Vince can answer judges' questions. Prefer simple, readable code over clever code.
- **Cost and secrets:** AI calls cost money. Say roughly what a run will cost before large runs. Never print, log or commit API keys. The key lives in `.env` (gitignored, mode 600). If a key is pasted in chat, say so, advise revoking it later, and never echo it.
- **Git:** do not commit or push unless asked. `git init` was run; no commits exist yet.
- **UI preferences from earlier projects:** calm, uncluttered interfaces; no automatic navigation or surprise redirects.
- Keep answers short and concrete. Report problems found in your own earlier work immediately and fix them.

## 4. Architecture at a glance

Everything the resident sees is exactly one of: (a) **copied verbatim** from an official source, (b) **computed by fixed rules** from open data, or (c) **written by AI and accepted only if software ties it to exact source text**. The three kinds are visibly labelled. AI generation happens **offline** and results are stored in `data/`. The web app itself never calls an AI model.

```
Sources -> parse -> stored JSON/SQLite in data/ -> FastAPI app (server-rendered, no JavaScript)
```

### Python package `triplens/`
| Module | Role |
|---|---|
| `app.py` | FastAPI routes: `/`, `/item/{id}`, `/access/{loc}`, `/route`, `/route/stops`, `/route/result`, `/route/example/{key}`; page assembly, caveats, examples |
| `labels.py` | Fixed plain wording for official item statuses (not AI) and `latest_stage` |
| `parse_item.py` | Parses a saved City item page into stages (body, date, status, wards), verbatim decision text, motions, vote totals, background documents, by-laws, upcoming flag, participation buttons. Keeps public communications as counts and dates only (no names) |
| `parse_report.py` | Extracts Summary, Recommendations, Financial impact, Decision history from staff-report PDF text with page numbers |
| `verify.py` | Confirms a quote appears in source pages (whitespace-insensitive) |
| `rewrite.py` | Claude rewrites passages into plain sentences; `check_sentence` enforces the rules in section 6 |
| `access.py` | Personas, stop lines (the exact text agents cite), nearby stops, rule-based flags, works lookup (road resurfacing and sidewalk programs) |
| `agents.py` | Three Claude agents with local tools; `verify_findings`, `dedupe`, `consolidate` (groups duplicates, writes no text) |
| `geocode.py` | Local SQLite address lookup built from City Address Points; normalization and nearby-number suggestions |
| `trip.py` | Loads route lines and ordered stops; `build_transit_leg` cuts the real line between the two stops the resident chose; `build_trip` adds straight-line walking legs |
| `exposure.py` | Decisions within 150 m and works within 120 m of the trip, decisions that name the route, fixed rider rules, ordering of flags |
| `changes.py` | Loads change files (verifies quotes against saved source text on load), applies effects to a trip, compares before and after |
| `svgmap.py` | Tile-free SVG drawing of the trip (no map service is contacted) |
| `templates/`, `static/style.css` | Jinja pages and styles |

### Scripts `scripts/` (all idempotent; run from the repo root)
`build_items.py`, `build_reports.py`, `build_plain.py` (API), `build_access_data.py`, `build_route_data.py`, `build_address_index.py`, `build_locations.py`, `run_audits.py` (API), `consolidate_audits.py` (API), `fill_readiness_report.py`.

### Data `data/`
| Path | Content | Committed? |
|---|---|---|
| `raw/*_snapshot.json` | Saved copies of official item pages (text, links, buttons) captured in a real browser | yes |
| `items/*.json` | Parsed items | yes |
| `reports/*.json`, `*.pages.json`, `index.json` | Extracted report passages and page text | yes (PDFs are gitignored) |
| `plain/*.json` | Checked AI rewrites with kept and dropped sentences | yes |
| `audits/*.json` | Stored agent runs (kept, dropped, every tool call text) with consolidation groups | yes |
| `notes/*.json` | Hand-written notes on source errors; exact winter-service sentences | yes |
| `locations.json` | Places for items (address matches or labelled representative points) | yes |
| `geo/stops.json`, `geo/routes.json` | Built from GTFS | built, not essential to commit |
| `geo/*.csv`, `geo/address.sqlite`, `gtfs/` | Downloaded open data (address CSV is about 180 MB) | **no** (gitignored) |

## 5. Setup and commands

Python 3.14 in `.venv`. Dependencies are in `pyproject.toml` (FastAPI, uvicorn, Jinja2, pypdf, anthropic, python-multipart; dev: pytest, httpx).

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
# secrets (never commit): .env containing ANTHROPIC_API_KEY=...   (only needed for build_plain, run_audits, consolidate_audits)

# downloads (Toronto Open Data, Open Government Licence - Toronto)
#   data/gtfs/ttc_gtfs.zip        "Merged GTFS - TTC Routes and Schedules"
#   data/geo/address_points.csv   "Address Points (Municipal)", file "Address Points - 4326.csv"
#   data/geo/street-furniture-transit-shelter.csv, street-furniture-bench.csv, road-resurfacing-program.csv, sidewalk-construction-program.csv  (4326 CSVs)

# build order
.venv/bin/python scripts/build_items.py
.venv/bin/python scripts/build_reports.py
.venv/bin/python scripts/build_plain.py            # API, a few cents
.venv/bin/python scripts/build_access_data.py
.venv/bin/python scripts/build_route_data.py
.venv/bin/python scripts/build_address_index.py
.venv/bin/python scripts/build_locations.py
.venv/bin/python scripts/run_audits.py             # API, about $0.18 per place and rider
.venv/bin/python scripts/consolidate_audits.py     # API, small
.venv/bin/python scripts/fill_readiness_report.py --name "..." --team "..." --email ... --member "Name|School|Program"

.venv/bin/uvicorn triplens.app:app --port 8765      # http://127.0.0.1:8765
.venv/bin/pytest -q                                 # 43 tests; run before saying anything is done
```

Item pages must be saved with a real browser (see section 8); there is no script for that step. The snapshot format is `{"fetched_at": ..., "items": {id: {"status": 200, "url", "text", "links": [{"text","href"}], "actions": [...]}}}`.

## 6. Trust rules (the core of the project; do not weaken)

1. **Copy, don't paraphrase** official wording: decisions, recommendations, report passages. Show page numbers and source links.
2. **AI output is untrusted until checked.** A rewritten sentence is kept only if (a) its quote is in the source passage (whitespace, quote-style and dash insensitive), (b) every number, date and amount in it appears in the source, and (c) it does not use stronger wording than the quote: `must, will, shall, only, required, requires, always, never, has to, have to, guarantee, guaranteed, promise, promised, definitely, all`. This stops "Council requested a study" becoming "Council must study". Dropped sentences are stored with a reason, never shown.
3. **Agent findings** must cite a tool result id and an exact quote from it, every number must appear in the cited text (or in the persona assumptions), and absolute or alarming words are banned (`always, never, guarantee(d), impossible, unsafe, dangerous, definitely, certainly, must, safe, accessible route`). **Agents may only label findings "watch" or "info"; only fixed rules in `access.py` and `exposure.py` may say "barrier"/"limit".** The consolidator may only return groups (a valid partition of indices), never text.
4. **Never infer a deadline.** For an upcoming item show the buttons the official page lists and link to the live page. Meeting dates are not deadlines. The City's "Agenda Deadlines" page is for staff and members, not the public.
5. **Distinguish** staff recommendation, committee decision and final Council decision, and "referred" from "decided".
6. **Personal information:** public letters and e-mails are counted, never named or quoted. Vote totals are kept, individual member names are not stored. Route-check addresses are never stored, logged or put in a URL.
7. **UI wording:** plain language, neutral. Do not say "safe", "possible" (about a trip), "accessible route", or advise what to do. Label estimates as estimates. Say what was not checked.
8. **Label AI.** AI-written text sits in a visibly labelled box with the supporting quotes one click away.
9. **Changes:** every real change file keeps exact quotes from a saved source file (`data/raw/...`); loading fails if a quote is missing. Simulated changes have `"simulated": true` and must be labelled "Simulation" on every page. Record the change status honestly (proposed vs decided vs implemented).
10. **Strong claims need evidence in the data.** Example: "No information" (GTFS 0) is not "not accessible" (GTFS 2); the page shows both.

## 7. Conventions

- Server-rendered HTML, **no JavaScript required**; WCAG-minded: semantic headings, labelled form fields, `role="alert"` for errors, text equivalents for drawings, keyboard focus styles, works on a phone, printable.
- **Jinja pitfall:** never name a dict key `items`, `keys` or `values` that a template reads with dot syntax; `d.items` resolves to the dict method. This bit twice (`loc.items`, `rep.items`). Use names like `item_ids` and `decisions`.
- Fixed rules live in code and are tested. Any new rule or AI feature needs tests and an entry in `docs/ai-use-log.md` (if AI is involved) and `docs/architecture.md`.
- Builds must be re-runnable. Do not hand-edit generated JSON except `data/notes/` and `data/locations.json` (edit `scripts/build_locations.py` instead where possible).
- Keep dependencies minimal. No analytics, no tracking, no external requests from the running app. Map tiles are deliberately not used.
- Python style: type hints where helpful, short functions, docstrings stating what a module guarantees. Avoid cleverness; Vince must be able to explain it.
- Use `.venv/bin/python` and run commands from the repo root.

## 8. Data sources and known quirks

| Source | Notes |
|---|---|
| City of Toronto meeting system (`secure.toronto.ca/council/agenda-item.do?item=ID`) | Plain scripted requests get **HTTP 403**; pages load in a real browser. Capture with a browser and save to `data/raw`. A real pilot needs a feed from the City Clerk. Item numbers in the new term look like `2027.PB1.6` although the meeting is in Nov 2026, so never parse the calendar year from an item number. |
| Staff reports (`toronto.ca/legdocs/mmis/...`) | PDFs extract cleanly with pypdf (no OCR). Large attachments (e.g. 152 pages, 15 MB) are skipped. Source errors exist (Dundas report says service "began on November 15, 2026" in a report dated June 2026); record them in `data/notes/`. |
| Toronto Open Data CKAN API | `datastore_search` returns at most 32,000 rows per call; page with `offset`. Voting Record and Report Request Log exist but are **not integrated** yet. |
| TTC GTFS | Only the current network is published (feed 2026-11-01 to 2026-12-19). Times can exceed 24:00 (after midnight on the same service day). Only service_ids 1, 2, 3 (weekday, Saturday, Sunday) are counted. **Every streetcar trip is flagged `wheelchair_accessible = 2` (not accessible)**, buses and subway mostly 1; the file does not explain this and the TTC may mean something different. A stop can list boarding as possible while all its trips are flagged not accessible. |
| Street furniture (shelters, benches) | Listed only if in the City dataset; "not listed" is not "none". |
| Road resurfacing and sidewalk programs | Lines with timeline text and last-updated dates; many timelines have ended or are stale. |
| Address Points | Local SQLite built from the 180 MB CSV. Normalization maps Avenue to Ave, strips unit prefixes and city names. |
| Winter maintenance report (item 2026.IE29.1) | Source of the exact winter sentences in `data/notes/winter_rules.json` (clearing starts at 2 cm, about 12 hours per cycle, laneways salted only). |
| Transitland archive of old TTC feeds | Requires an API key; sources disagree on whether the free plan covers downloads. Not used. Before/after comparison is therefore not built. |
| Reddit | Blocked for the search tool. |

Walking distance everywhere is straight line times **1.3** (an assumption). Persona walking limits (wheelchair 400 m, senior with cane or walker 250 m, shift worker 600 m) are illustrative, not medical or legal definitions.

## 9. Testing

`pytest -q` must pass before reporting work done (50 tests). Coverage:
- `test_parse_item.py`: parsing is verbatim, stages ordered, amendments and votes, no names of letter writers.
- `test_report_and_upcoming.py`: extracted report passages exist in the PDF text; Dundas staff recommendation differs from the decision; upcoming items have buttons and no invented deadline.
- `test_rewrite_checks.py`, `test_plain_store.py`: the sentence checker (quotes, numbers, strengthened wording) and re-verification of every stored sentence and staleness against current text.
- `test_access_agents.py`: persona rules, agent verifier (bad quotes, numbers, banned words, agents cannot label a barrier, dedupe), stored audits pass verification, groupings are valid partitions.
- `test_route_check.py`: address normalization, stop-order checks, real route line, decisions found along the Queen trip, the 505 "decision names your route" flag with a real quoted snippet, ended works downgraded, evidence on every flag, decided items never shown as open, bad-input messages, and the privacy test (no files written, no cookies, no address in the URL), and that the tool never picks stops for the resident.

When changing any rule, update the test that guards it. If a stored AI file is regenerated, rerun `pytest`.

## 10. Status (update when this changes)

**Built:** explain layer; staff-report extraction; AI rewrites with checks (11 items); rider access page with three personas and 15 stored audits across 5 places; route check with four examples; local address lookup; tile-free drawing; privacy test; docs (`architecture.md`, `route-check-architecture.md`, `ai-use-log.md`, readiness draft and filled Word template).

**Built (Nov 13):** before/after comparison for structured changes (one real TTC proposal, one simulation).

**Not built:** trip timing; reroutes onto new streets (no stop data for them); automatic extraction of change effects from reports (effects are entered by hand with quotes); routing; AI-written reports for route-check examples; the return trip; transfers beyond two routes; translation; ingestion without a browser; Voting Record and Report Request Log integration; location data for most items (11 items located); user testing with accessibility groups.

**Still owed by the owner (deliverables and review):** choose the final name and rerun `fill_readiness_report.py`; open the Word file, check it fits one page, save as PDF; record the 2 to 3 minute demo video; write the Devpost description; read the AI rewrites and audit findings for the demo items and tick the boxes in `docs/ai-use-log.md`; make the first git commits and push; revoke the API key after the hackathon.

## 11. Mistakes already made (do not repeat)

- Said the idea was "unique enough" before searching prior art. Agency "compare my trip" tools exist (Houston, Baltimore, WMATA, MBTA, others). Differentiation is persona-based accessibility, the decision-process layer, and checked claims.
- Described a Spadina Road council item as "reversed". It was **replaced** by a revised two-phase plan starting March 2027.
- Read the TTC trip accessibility flag as a single percentage, which confused "no information" with "not accessible".
- Let agents label individual stops "barrier" (e.g. a disused bus bay). Only fixed rules may.
- Added a stop "suggestion" that picked the shortest walks, which nobody asked for.
- Wrote a heredoc with escaped quotes that failed silently and left code half-edited. Verify every scripted edit applied before relying on it.
- Let a Jinja template read `d.items` on a dict.
- An early draft listed datasets and claims the app does not use. Only list what is integrated.

## 12. Recipes

**Add an item:** save its page with a browser into `data/raw/*_snapshot.json`; run `build_items.py`, `build_reports.py`, `build_plain.py <item_id>`; add a location in `scripts/build_locations.py` if it has a place; rerun it; review the rewrite by hand; add a test if it exercises a new case.

**Add a persona rule:** edit `access.py` (rider page) and/or `exposure.py` (route check); keep text neutral and evidence-backed; add a test; if the TTC data is involved, state its limits on the page.

**Add an example trip:** add an entry to `EXAMPLES` in `app.py` with explicit `stops` (variant index, boarding stop id, exit stop id per route). Use public landmarks, not a person's home. Check the result by hand.

**Change the AI rules:** edit `rewrite.py` or `agents.py`, add a failing test first, rerun the stored-file tests, update `docs/ai-use-log.md`.

**Rename the project:** change the title in `triplens/templates/base.html`, the README and docs, `scripts/fill_readiness_report.py --name`, and the Devpost text.

## 13. Glossary

- **Item:** one agenda item (for example `2026.TE34.104`). **Stage:** one body's consideration of it (Community Council, then City Council).
- **TMMIS:** the City's meeting management system that hosts item pages.
- **GTFS:** the standard transit schedule feed. `wheelchair_boarding` is on stops (1 possible, 2 not possible, 0 no information); `wheelchair_accessible` is on trips with the same meanings.
- **Persona / rider:** an illustrative rider profile with a walking limit and rules, not a real person.
- **Corridor / leg:** one piece of a trip; walking legs are straight lines, transit legs follow the route's real line.
- **Verifier:** the code that rejects AI text it cannot tie to the source.
- **Barrier / limit:** wording reserved for fixed rules.

**Add a change:** save the official source text into `data/raw/`; create `data/changes/<id>.json` with `title, body, status, status_note, simulated, source_url, source_file, quotes[], effects[]` (effect types: `remove_stop`, `remove_shelter`, `remove_bench`, each with `route`, `stop_ids`, `quote`); stop ids come from `data/geo/routes.json`; run the tests (quotes are verified on load).
