# Gait: complete project overview

Written Nov 14, 2026 (00:30 ET) from the code, data and docs as they stand. This document describes everything that is built, how it fits together, what is not built, and what is still owed before the 10:00 am deadline. For the research history, see `README.md`. For the rules AI assistants follow, see `CLAUDE.md`.

---

## 1. In one paragraph

Gait is a web app made for **FCI CIVIC Hack 2026, Challenge 1: "Making municipal decisions easier to understand."** It takes real City of Toronto council decisions and shows what they mean for **one resident's own bus or streetcar trip**, seen through a specific rider: a **wheelchair user**, a **senior using a cane or walker**, or a **shift worker**. Every claim on screen is one of three kinds: (a) **copied word for word** from an official source, with its page number, (b) **computed by fixed rules** from open data, or (c) **written by AI and kept only if software can tie it to exact source text**. The three kinds are labelled differently on the page.

**Pitch:** *Your route, your rider, before the vote.*

**Headline example (real):** City Council approved road and sidewalk closures to build the Ontario Line's Cosburn Station (item 2025.EX27.3, staff report page 17). For a senior using a walker starting on Cosburn Avenue, the walk to the 72 Pape stop goes from **about 118 m to about 288 m**, measured along the City's sidewalk network.

---

## 2. Who it is for, and the problem

- **Residents who depend on transit and have accessibility needs.** They often learn what a decision means for them only after it happens: a stop disappears, a shelter goes, the walk gets longer.
- **Clerks and councillors' staff** who explain decisions to residents.

The problem: decisions are buried in long reports, the difference between "staff recommended", "committee decided" and "Council decided" is easy to miss, comment windows are easy to miss, and agency summaries describe an *average* rider ("99.4% keep a stop within a quarter mile"), which hides the people a change hurts most.

**Prior art:** agency "compare my trip" tools exist (Houston, Pittsburgh, WMATA, MBTA, Baltimore, others). Gait is different in three ways: rider-based accessibility, the decision-process layer, and checked claims.

---

## 3. What the app does: every page

Run the app and open http://127.0.0.1:8765.

### 3.1 Landing page: `/`
- A scroll story in six scenes. As you scroll, a drawing of the earth sewn from fabric patches turns, scene by scene. Each scene has its own background colour (harvest gold, avocado, burnt orange, white, turquoise). The design notes are in `DESIGN.md`.
- The scenes: (0) "See what changed on your bus trip." (1) the rider's short walk before, **118 m** (2) the Cosburn Station construction, **288 m** (3) shelters and **12,834** 311 reports this year (4) "Every fact has its page number," with a real quote from the staff report (5) "Now check your own trip," with the **Check my bus trip** button.
- The figures are computed live by `gait/landing.py` from the same trip engine and change files as the map. Nothing is typed in by hand.
- Changes on Nov 13–14: the footer was removed, so scrolling ends at the last scene. The "Use a simple form instead" link was removed. The orange-to-white fade was slowed to 1.8 s (`--fade` on `body.sc3`).
- Respects reduced motion (no snow, no animated turning).

### 3.2 3D map: `/map` (the main tool)
- MapLibre with OpenFreeMap tiles, tilted 3D buildings.
- **Set up the trip:** click the start and the destination. The app lists the routes that have stops within 800 m of both (by number, not ranked). Choose one, then click your own boarding and exit stops, then pick the rider, the day and the time of day. **The tool never picks stops or routes for you.**
- **Results in four pages** (Back / Next, "Edit trip" goes back):
  1. The trip as you set it up: walking legs on the City pedestrian network, shelters (blue boxes) and benches (brown) in 3D.
  2. What changes for the trip: the verdict and the before (blue) and after (orange) rows, with a toggle. Removed stops are shown as red rings.
  3. What the City wrote: the browser calls `/api/source_check`, which re-reads each quote on its cached source page and shows the page and the surrounding text. If a quote can't be found again, it shows "Not found". This is a real check, not an animation.
  4. What people report on the new part: City 311 requests and rider reports, with the report writer.
- **Map overlays:** "Street and transit changes" shows where decisions land: dashed bubbles around affected places, × on removed or closed stops, closed sidewalks and roads as thick dashes. Real decisions are always shown; simulations only with their own trip.
- **City works on your route:** road resurfacing and sidewalk construction listings, kept only if their street section touches the trip (within 20 m of a walk, within 30 m of a stop, or 80 m or more along the ride) and their timeline has not ended.
- **Trip impact report:** a plain-text report (facts, quotes, 311, checked findings, and a blank "In my own words" section) that you can copy, email (a mailto link, so the tool sends nothing) or print. It also lists where to send it: the council item page, your councillor via the City's lookup page plus your ward, 311, and TTC Customer Service. It names no councillors and gives no deadlines.
- **Optional live research** (a button): see 6.3.
- **Sample trips** (`/map?sample=<key>`):

| Key | Change shown | Real or simulated |
|---|---|---|
| `cosburn` | Ontario Line Cosburn Station construction: Pape west sidewalk closed, southbound stop moved | Real, in effect |
| `bathurst` | RapidTO (July 2025) removed three 7 Bathurst stops. Senior with walker: about **62 m before, 419 m today** | Real, implemented |
| `dufferin` | RapidTO removed the 29 Dufferin stop at Croatia St | Real, implemented |
| `harbord` | Harbord–Hoskin bikeway: 94 stops shifted, bus/bike platforms. Wheelchair user: 89 m to 129 m | Real, implemented |
| `frontst` | Front St West lay-by: new shelter and relocated accessible loading zone (114/121) | Real, approved |
| `queen` | Shelters removed at two Queen St West stops | **Simulation** |
| `dundas` | 505 stop at Grace St moved about 220 m east | **Simulation** |
| `spadina` | 127 stops at Bernard and Kendal closed during construction | **Simulation** |
| `late` | Late-night 7 Bathurst trips cut by half | **Simulation** |

### 3.3 Route check, form version: `/route`
The no-JavaScript version of the map. Flow: `/route` (start, destination, route(s), rider, day, time) → `/route/stops` (choose your stops) → `/route/result`. The result shows decisions within 150 m of the trip, works within 120 m, decisions that name your route, how your stops work for your rider, and a before/after table when a change applies. A tile-free SVG drawing replaces the map. Examples at `/route/example/<key>`: `queen-beverley`, `dundas-505`, `spadina-127`, `bathurst-7-past`, `transfer-late`.
*(The landing page no longer links here; the page still works.)*

### 3.4 Council decisions: `/decisions` and `/item/<id>`
- `/decisions` lists 11 real items: 5 decided or referred, and 6 upcoming Toronto Preservation Board items (meeting `2027.PB1`, Nov 16, 2026).
- `/item/<id>` shows where the item stands (fixed plain labels), the **staff recommendation next to the decision**, the wards, whether the official page shows **Request to Speak / Submit Comments** buttons (with a link to the live page, never an invented deadline), the process timeline, exact report quotes with page numbers, an **AI plain-language box** with the supporting quotes one click away, and a "What this page can't tell you" section.
- Good demo items: `2026.TE34.104` (505 Dundas: staff only recommended "receive for information", and Council asked for more), `2026.IE31.8` (laneway snow: *referred*, not decided), `2026.TE32.25` then `2026.MM42.46` (Spadina Rd: decided on consent, then **replaced** by a two-phase plan, not reversed), `2027.PB1.6` (1337 Queen St W, still open for comments).

### 3.5 Rider access: `/access/<location>?persona=...`
For each of 5 places linked to an item, compares transit access for the three riders: nearby stops, boarding flags, trip accessibility flags (all three values shown), shelters and benches, service at the chosen time, and fixed-rule flags. Below that are the **checked findings of three AI audit agents** (15 stored audits: 5 places × 3 riders).

### 3.6 Past-decision research: `/research/<route>`
Shows, for a route, the sentences from 1,091 indexed staff reports that match change patterns ("free research", no AI), then any findings from the research agent. This is how the RapidTO and other past decisions were found. A person then turns a finding into a change file.

### 3.7 JSON endpoints (used by the map)
`/api/routes_near`, `/api/route_stops`, `/api/trip` (POST), `/api/decision_areas`, `/api/developments`, `/api/source_check`, `/api/research_trip` (POST), `/api/report_categories`, `/api/report` (POST).

---

## 4. What it deliberately does NOT do

- It does **not** plan trips, time trips, or suggest routes, stops or alternatives. (A "shortest walk" stop suggestion was added once and removed.)
- It does **not** recommend, take sides, or say a trip is "possible", "safe" or "accessible". It stays neutral, as the brief requires.
- It does **not** infer deadlines. Meeting dates are not deadlines.
- It does **not** store anything about a user's identity: no accounts, cookies, analytics, or address logs. Addresses never appear in URLs. **One exception:** rider reports (see 6.4) store a category, a rounded point, a stop id and a date.
- It does **not** read proposed-network schedules (none are published). Before/after works only for changes entered by hand as structured effects with quotes.

---

## 5. Architecture

```
Official sources ──► parse / build scripts ──► stored JSON + SQLite in data/ ──► FastAPI app (server-rendered Jinja pages + map JSON API)
                                   ▲
                    offline AI (rewrites, agents), each output verified before storing
```

**Why this shape:** AI generation runs offline and the results are stored, so the demo is repeatable and no unchecked answer can appear live. The one exception is the opt-in live research button, which is verified in the same way before anything is shown.

### 5.1 Python package `gait/` (about 3,700 lines)

| Module | Lines | What it does |
|---|---|---|
| `app.py` | 703 | All FastAPI routes, page assembly, caveats, example trips |
| `changes.py` | 482 | Loads change files (fails if a quote is missing from its source), applies effects to a trip, compares before and after, writes the plain sentences for each difference |
| `access.py` | 348 | Riders (wheelchair 400 m, senior with cane or walker 250 m, shift worker 600 m), stop lines agents cite, nearby stops, rule-based flags, works along the trip |
| `exposure.py` | 333 | Decisions within 150 m, works within 120 m, decisions that name the route, fixed rider rules, ordering of flags |
| `agents.py` | 325 | Three Claude audit agents with five local tools; `verify_findings`, `dedupe`, `consolidate` (groups only) |
| `parse_item.py` | 274 | Saved item page → stages, verbatim decision text, motions, vote totals, documents, by-laws, upcoming flag, buttons. Public letters kept as counts and dates only |
| `reports.py` | 173 | 311 requests and rider reports near the trip; search trace; staff-report leads |
| `research.py` | 167 | Research agent for past decisions (three tools over the Voting Record, Report Request Log and report PDFs) |
| `rewrite.py` | 157 | Claude plain-language rewrites; `check_sentence` enforces the trust rules |
| `live_research.py` | 157 | Opt-in live RAG for a trip: retrieve, Claude writes at most 4 findings, code verifies each |
| `walk.py` | 150 | Walking routes on the City Pedestrian Network; wheelchair and walker riders avoid segments with no sidewalk; flags metres with no sidewalk and unsignalled crossings |
| `finder.py` | 125 | Free (no AI) search of the SQLite full-text index for each route's streets |
| `landing.py` | 118 | Landing-page figures from the real trip engine |
| `parse_report.py` | 95 | Staff report PDF → Summary, Recommendations, Financial impact, Decision history, with page numbers |
| `trip.py` | 91 | Route lines and ordered stops; cuts the real line between the two stops the resident chose |
| `geocode.py` | 79 | Local SQLite address lookup built from City Address Points |
| `svgmap.py` | 48 | Tile-free SVG trip drawing |
| `labels.py` | 37 | Fixed plain wording for official item statuses |
| `verify.py` | 21 | Confirms a quote appears in source pages (ignores differences in whitespace, quote marks and dashes) |

Templates: `landing, map, base, index, item, access, research, route_form, route_stops, route_result`. Styles: `static/style.css`; fonts are self-hosted in `static/fonts`.

### 5.2 Build scripts `scripts/` (all re-runnable; run from the repo root)

| Script | Builds | Uses AI? |
|---|---|---|
| `build_items.py` | `data/items/` from saved item pages | no |
| `build_reports.py` | `data/reports/` passages with page numbers | no |
| `build_plain.py` | `data/plain/` checked rewrites | **yes**, a few cents |
| `build_access_data.py` | `data/geo/stops.json` (GTFS + shelters + benches) | no |
| `build_route_data.py` | `data/geo/routes.json` (shapes, ordered stops) | no |
| `build_address_index.py` | `data/geo/address.sqlite` | no |
| `build_locations.py` | `data/locations.json` | no |
| `run_audits.py` | `data/audits/` | **yes**, about $0.18 per place and rider |
| `consolidate_audits.py` | grouping of duplicate findings | **yes**, small |
| `build_corpus.py` | SQLite full-text index of 1,091 report PDFs from 401 items | no |
| `run_free_research.py` | `data/research_free/` for all 230 routes (about 4 min) | no |
| `run_research.py` | `data/research/` (agent) | **yes** |
| `build_311.py` | 311 requests placed at the nearest intersection | no |
| `build_developments.py` | `data/developments.json` (47 rezonings, quotes checked) | no |
| `fill_readiness_report.py` | `docs/readiness-report.docx` from the organizers' template | no |

### 5.3 Data `data/`

| Path | Contents |
|---|---|
| `raw/` | Saved official item pages (`items_`, `live_`, `past_snapshot.json`), 311 raw data, saved TTC text |
| `items/` (11), `reports/`, `plain/` (11) | Parsed items, report passages and page text, checked AI rewrites (kept and dropped sentences with reasons) |
| `audits/` (15) | Stored agent runs: kept and dropped findings, and the text of every tool call |
| `changes/` (10) | Structured changes: 5 real, 5 simulated (table in 3.2) |
| `changes_retired/` | TTC 512 St Clair stop removals, retired Nov 13 (it was a TTC proposal, not a Council decision, and its March 2026 date could not be confirmed) |
| `notes/` | Hand-written notes on source errors; the exact winter-service sentences |
| `records/` | Voting Record and Report Request Log (used by the research agent) |
| `research/`, `research_free/` (230), `research_live/` (8 cached trips) | Research results |
| `developments.json`, `locations.json`, `geo/` | Rezonings, item places, GTFS-derived stops and routes, pedestrian network |
| **Not committed** (gitignored) | GTFS zip, the 180 MB address CSV and its SQLite, the pedestrian network CSV and graph, report PDFs, the corpus index, `rider_reports.sqlite`, `.env` |

---

## 6. How AI is used, and how it is checked

### 6.1 Plain-language rewrites (`rewrite.py`, offline)
Claude (`claude-opus-5-5`) rewrites each Summary, Recommendation and Decision passage into 2 to 6 short sentences, each carrying an exact quote. Software **drops** a sentence if:
1. its quote is not in the source (the check ignores differences in whitespace, quote style and dashes),
2. it contains a number, date or amount not in the source, or
3. it uses stronger wording than its quote: `must, will, shall, only, required, requires, always, never, has to, have to, guarantee(d), promise(d), definitely, all`. This stops "Council requested a study" from becoming "Council must study".

Dropped sentences are stored with the reason and never shown. Long passages carry a warning that the sentences cover only the main points.

### 6.2 Access-audit agents (`agents.py`, offline)
Three agents per place and rider (stops and boarding; walking and winter; service and schedule), each limited to **five local tools** with no internet access. A finding is kept only if it cites a tool result id and an exact quote from that result, every number in it appears in the cited text, and it uses none of the banned words (`always, never, guarantee(d), impossible, unsafe, dangerous, definitely, certainly, must, safe, accessible route`). **Agents may only label findings "watch" or "info". Only fixed rules may say "barrier" or "limit."** A consolidator call returns only groups of duplicate findings (checked to be a valid partition) and cannot add text. The first run cost about $2.80 for all 15 audits.

### 6.3 Live research (`live_research.py`, the only AI call the running app makes)
This runs only when the rider presses the button. It retrieves passages from the full-text index: sentences found by the finder, plus pages that name the rider's own stop streets. Claude writes at most 4 findings, and code verifies each one (quote on the cited page, no new numbers, no stronger wording, no banned words). **The address is never sent.** Results are cached per trip. Each new trip costs about 2 cents.

### 6.4 Research agent for past decisions (`research.py`, offline)
Searches the Voting Record and Report Request Log and reads passages from City PDFs. A finding is kept only if its quote is on the cited page. A person turns findings into change files by hand. It found RapidTO item 2025.EX25.4 (7 Bathurst and 29 Dufferin stop removals).

### 6.5 AI used to build the code
Claude Code wrote most of the Python, templates and tests from requirements discussed with Vince. The record is in `docs/ai-use-log.md`, which still has boxes for Vince's own review (see section 10).

### 6.6 Never done by AI
Decision wording, recommendations, dates, votes, statuses, wards, distances and every number in the rider tables are copied or computed by fixed code.

---

## 7. Trust and privacy rules (the core of the project)

1. **Copy, don't paraphrase** official wording; show page numbers and links.
2. **AI output is untrusted until checked** (section 6).
3. **Only fixed rules say "barrier"/"limit."**
4. **Never infer a deadline.** Show the buttons the official page lists and link to it.
5. **Keep staff recommendation, committee decision and Council decision distinct**, and keep "referred" distinct from "decided".
6. **Personal information:** public letters are counted, never named or quoted; individual councillors' votes are not stored; addresses are not stored, logged or put in a URL. A test checks that a route check writes no file and sets no cookie.
7. **Neutral wording:** the app never says "safe", "possible" (about a trip) or "accessible route", and gives no advice. Estimates are labelled as estimates, and each page says what was not checked.
8. **AI is labelled** in a visible box, with the quotes one click away.
9. **Changes keep exact quotes** from saved sources (a file fails to load if a quote is missing). Simulations are marked `"simulated": true` and labelled "Simulation" everywhere.
10. **Strong claims need evidence.** GTFS "no information" (0) is never shown as "not accessible" (2).

---

## 8. Data sources (all public and open)

| Source | Used for | Known quirk |
|---|---|---|
| City of Toronto meeting system (item pages) | Items, stages, buttons | Returns HTTP 403 to scripts, so pages were saved with a real browser. A pilot needs a Clerk feed. Item numbers like `2027.PB1.6` belong to a Nov 2026 meeting, so the year can't be read from them |
| City staff reports (legdocs PDFs) | Quotes and page numbers | Extract cleanly; some source errors (the Dundas report says service "began on November 15, 2026" in a report dated June 2026), recorded in `data/notes/` |
| TTC GTFS (merged feed, Nov 1 to Dec 19, 2026) | Stops, routes, service, accessibility flags | **Every streetcar trip is flagged not accessible (2)** with no explanation; the page says so. Only the current network is published |
| Street furniture: shelters, benches | Shelter and seating | "Not listed" is not "none" |
| Road resurfacing and sidewalk construction programs | Works along the trip | Many timelines have ended; ended works are left out or marked as ended |
| Address Points | Local address lookup | 180 MB CSV → SQLite |
| Pedestrian Network | Walking routes | The City warns it has "known limitations in completeness" |
| 311 service requests | Reported problems near the trip | History, not current conditions |
| Voting Record, Report Request Log | Research agent | |
| Winter maintenance report (item 2026.IE29.1) | Exact winter sentences (clearing starts at 2 cm, about 12 hours per cycle, laneways salted only) | Service levels, not the state of a given sidewalk |

Licence: Open Government Licence – Toronto. **Note:** the landing page's footer, which carried this credit and the "not an official City or TTC service" line, was removed on Nov 14. Consider putting both back as one line of small print, or check that another page carries them.

**Assumptions:** the riders' walking limits (400 / 250 / 600 m) are illustrative, not medical or legal definitions. When no sidewalk path is found, walking distance falls back to a straight line × 1.3.

---

## 9. Testing

`.venv/bin/pytest -q`: **74 tests pass** (as of Nov 14, 00:20). They cover:

- `test_parse_item.py`: parsing is verbatim, stages are in order, amendments and votes, no names of letter writers.
- `test_report_and_upcoming.py`: report passages exist in the PDF text; the Dundas recommendation differs from the decision; upcoming items have buttons and no invented deadline.
- `test_rewrite_checks.py`, `test_plain_store.py`: the sentence checker; every stored sentence is re-verified; a stored rewrite counts as stale when the official text changes.
- `test_access_agents.py`: rider rules, the agent verifier (bad quotes, numbers, banned words, the barrier ban, dedupe), stored audits pass verification, groupings are valid partitions.
- `test_route_check.py`: address normalization, stop order, real route line, decisions along the trip, the 505 "names your route" flag, ended works downgraded, evidence on every flag, the privacy test, and that the tool never picks stops.
- `test_reports.py`: 311 and rider reports, the rezoning quotes checked against the index.
- `test_live_research.py`: the live research verifier.

---

## 10. How to run it

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn gait.app:app --port 8765     # http://127.0.0.1:8765
.venv/bin/pytest -q
```
An API key in `.env` (`ANTHROPIC_API_KEY=...`, gitignored) is needed only by the AI build scripts and the live research button. The full rebuild order and download list are in `CLAUDE.md` section 5.

---

## 11. Not built (say so if asked)

Trip timing; reroutes onto new streets; automatic extraction of change effects from reports (effects are entered by hand with quotes); routing; the return trip; transfers beyond two routes; translation; loading items without a browser (needs a Clerk feed); location data for most items (11 placed); testing with accessibility groups; curb-ramp, tactile-paving, slope and snow-state data (none found in open data).

---

## 12. Deliverables: status at 00:30 Nov 14 (deadline **10:00 am today**)

| Deliverable | State | What's left |
|---|---|---|
| Code repo (commits are checked) | 26 commits on `main`, last at Nov 13 14:33. **About 36 files are uncommitted**, including all of today's work | Commit, create the GitHub repo, push, check it is public |
| Demo video (2–3 min, over 3 min isn't considered) | Script in `docs/devpost-and-video.md` (target 2:40) | Record at 1280 px, 125% zoom; rehearse once with a timer |
| Municipal Readiness Report (one page, PDF) | Text in `docs/readiness-report-draft.md`; Word file `docs/readiness-report.docx` | Update outdated lines (below), check it fits one page, save as PDF, add to the repo and Devpost |
| Devpost description | Draft in `docs/devpost-and-video.md` | Paste, add the links |
| AI-use review | `docs/ai-use-log.md` has unticked boxes and a "Replace this line" blank | Read the demo items' rewrites and findings, tick the boxes, fill in the blank |
| After the hackathon | | Revoke the API key |

### Docs that no longer match the code (fix before submitting)
- **Readiness report** says "Mocked: real sidewalk paths, before/after comparisons". Both are built now (`walk.py`, `changes.py`). Only translation and live item loading are still not built.
- **`README.md`** opens with "Status: idea stage" and says "No 3D" in its early plan. Both are out of date: the app is built and `/map` is 3D.
- **`CLAUDE.md`** says "no commits exist yet" (there are 26), and gives two different test counts (43 and 54; the actual count is 74).
- **`docs/architecture.md`** section 6 says walking is a straight line × 1.3 and the sidewalk network is not modelled. That is now only the fallback.
- **"New buildings approved"**: `CLAUDE.md` still describes it as a map toggle. It is no longer on the map (`map.html` doesn't use it); only `/api/developments` remains, as `docs/architecture.md` says.
- The Devpost draft's "Check my route" bullet describes the form; the main tool is now the map.

---

## 13. Likely judge questions, with short answers

- **"How do you stop the AI from making things up?"** Every AI sentence must carry an exact quote that software finds in the source. Numbers must match, and wording can't be stronger than the quote. Anything that fails is dropped and stored with a reason. Show `rewrite.check_sentence` and `tests/test_rewrite_checks.py`.
- **"Is the 118 m → 288 m real?"** Yes. The closure comes from item 2025.EX27.3 (quote on page 17). The distances are walks on the City Pedestrian Network to the old and new stop, computed by `walk.py`. They are labelled "about".
- **"Why not just use a trip planner?"** Trip planners plan for an average rider and say nothing about council decisions. Gait doesn't plan. It shows what a decision changes for the trip you already take, for your kind of rider, with the source.
- **"Why are some examples simulated?"** Proposed networks aren't published as data. Simulations show the other change types (shelter removal, relocation, closure, service cut) and are labelled on every page. Five examples are real Council decisions.
- **"What would a city need to adopt it?"** An agenda feed from the Clerk, a GTFS feed (a standard), open address and sidewalk data, its own participation rules, and rider limits set with local accessibility groups.
- **"What does it store about me?"** Nothing from the trip. Rider reports are the one exception: category, rounded point, stop id and date, and temporary ones expire.
