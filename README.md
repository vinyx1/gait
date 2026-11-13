# TripLens — project brief (working title)

**Event:** FCI CIVIC Hack 2026, Challenge 1: *Making municipal decisions easier to understand*
**Status:** idea stage. Everything under "To verify" is untested.

## One-line pitch
Existing tools tell an average rider how a proposed change affects their trip. TripLens tells the people averages hide (a senior with a walker, a wheelchair user in January, a shift worker at 11 pm) whether they are still served, with every claim linked to its source, and ties the result to the council process so they know when and how to respond.

## The problem it answers
- Residents learn about decisions after they are made. Example: in Sault Ste. Marie, a retired teacher timed the new Sault Loops routes herself. Her weekly trip to church went from about 5 to 49 minutes, and she worries about walking to other stops in winter ([SooToday, Jun 30 2026](https://www.sootoday.com/local-news/if-i-break-a-hip-its-game-over-senior-stages-protest-over-bus-route-changes-12491009)).
- Agency summaries use averages. Pittsburgh's agency reported that 99.4% of current riders keep service within a quarter mile of their existing stop ([PRT](https://engage.rideprt.org/buslineredesign/draft-network-1-system-map)). A quarter mile is a design choice that excludes some people.
- Brief stats: only 20% of Canadians have taken part in a municipal consultation; Ontario municipal turnout was about 36% in 2022.

## Prior art (what already exists)
| Tool | What it does | Gap seen |
|---|---|---|
| Houston side-by-side planners ([Human Transit](https://humantransit.org/2015/06/houston-see-how-your-new-transit-system-compares-to-the-old.html)) | Compares one trip on the old vs. new network | Write-up does not mention walking ability, wheelchair access, time of day or mobility; trip-by-trip only |
| Pittsburgh DIY calculator ([PPT](https://www.pittsburghforpublictransit.org/?p=9501)) | Uses Google Maps driving time plus a transfer penalty | Page does not mention accessibility, seniors, disabilities or night/weekend service |
| WMATA, MBTA, Baltimore, AC Transit, MTA Queens | Agency compare-my-trip tools | Not checked (WMATA page blocked; Queens link now redirects) |

Caveat: this is a small sample from search summaries, not a full survey. A basic before/after trip comparison is not new. Differentiation must come from the points below.

## What is different
1. **Persona-based accessibility.** Each trip is judged against constraints, not an average rider.
2. **Barrier outcomes, not just times.** Results include "trip no longer possible" and "can't tell (missing data)", and also show gains, to stay neutral.
3. **Access-auditor agents.** AI agents gather and check evidence about a route (see below).
4. **Tied to the decision process.** Status (staff recommendation / committee / council), next date to act, link to the official item page, and a comment draft built from the trip numbers.
5. **Staff view.** Run a proposal across sample personas and destinations before the vote and see who loses most.

## Users and personas
| Persona | What is computed |
|---|---|
| Senior with cane/walker | Longest single walk vs. their limit (adjustable), shelter/seating at transfers, winter penalty |
| Wheelchair user | Accessible boarding and transfer stops only, sidewalk and curb-ramp presence, snow factor |
| Shift worker | Last departure home, first bus out, night frequency, transfer waits |
| Newcomer/renter | Plain-language and translated output, printable sheet, no-car assumption, notice gaps |

Limits (max walk, winter on/off, time of day) are user-adjustable.

## How it works
- **Input:** address (processed in the browser, not stored), up to 3 saved trips, persona.
- **Routing (deterministic):** schedule data plus OpenStreetMap, run on the old and the proposed network. All times, transfers, walk distances and reach areas come from here. AI never produces these numbers.
- **Journey strip (core UI):** step-by-step before/after timeline with a barrier flag on each step. Text-first so it works with screen readers and prints.
- **2D map:** both routes, friction-point markers, and a reach overlay. Optional openly licensed street photos at friction points. No 3D.
- **Decision panel:** what is proposed and why, who decided what, key dates and how to comment (verified on the official item page, never inferred from a meeting date), source passage for each claim.
- **Outputs:** large-type printable sheet, text-only version, comment draft.

## Access-auditor agents
| Agent | Searches | Example finding |
|---|---|---|
| Stop auditor | Schedule data (accessibility flag), OSM tags (shelter, bench, kerb, tactile paving) | "Stop X has no shelter; boarding accessibility unknown" |
| Walk-leg auditor | Sidewalk presence, slope, surface, crossings | "Leg 2 crosses a 6-lane road, no signal tagged" |
| Maintenance/winter | Snow-clearing priority, construction/closure notices, 311 | "Low priority for sidewalk clearing" |
| Schedule auditor | Last departure, headways at the persona's time | "Last bus home 10:42 pm" |
| Document agent | Council reports, accessibility committee minutes, news | Quoted passage with link |
| Verifier | Re-checks every claim against its source | Drops unsupported claims |

Rules: each finding carries a source link, date and confidence. Missing data is "unknown", never "accessible". Photo-based findings read "possible issue seen in a photo dated X, unverified".

## How it meets the brief
- Plain language: proposal, why, who and where it affects ("near me").
- Key dates and how to have a say, verified on the official item page.
- Source link and date for every explanation; staff recommendation vs. committee vs. council kept distinct.
- Summaries preserve conditions and uncertainty; AI role stated and checked against records.
- Thought about who it leaves out: offline users (printable sheet), low literacy and limited English (plain language, translation), screen-reader users (text-first, WCAG).
- Data minimization: address stays in the browser; route geometry sent to outside services is trimmed or rounded.
- Datasets: Report Request Log and Council Voting Record (Toronto) to show decision history and vote context. Read motions carefully; a vote may be on an amendment, and not every decision has a recorded vote.
- Test on 2-3 real agenda items.

## Two layers
- **Explain layer (works on any item):** what is proposed and why, which body decides, status (staff recommendation / committee / council), amendments, dates and how to comment (verified on the official item page), a source passage for every claim. Must follow attachments, not just the cover report.
- **Impact layer (plugs in where an item has a footprint):** the trip lens and audit agents. For items with no spatial effect it says "no personal impact module for this type, explanation only."

## MVP scope and build order (cut from the bottom)
1. Explain layer on 2-3 real items, including one non-transit item.
2. Status timeline, amendments, dates, official links.
3. Trip lens on one transit item (address, up to 3 trips, persona, before/after journey strip with ranges and stated assumptions).
4. Two or three audit agents plus the verifier.
5. Comment draft (neutral: states facts about the trip; the user chooses support/oppose/neutral).
6. Staff "who loses" view (shows gains as well as losses).

Cut: accounts, notifications, 3D, real-time crowd simulation, wheelchair physics, ingesting every agenda.

## Demo plan
- **Replay:** an already-implemented change with real before/after schedule feeds, to prove accuracy.
- **Live:** a real agenda item to show the process layer.
- Precompute agent reports for demo decisions; run agents live only for custom trips, with visible progress.

## Risks
- **Proposed networks are rarely published as data.** Decides what can be demoed.
- **Sparse open data** (stop accessibility, sidewalks, curb ramps) could leave agents reporting mostly "unknown".
- **Hallucination.** Mitigation: quoted sources, verifier, separate "not verified" section.
- **Terms of service** for street imagery. Use openly licensed imagery; check terms.
- **Liability.** Frame as an evidence report, not a guarantee of safe travel.
- **Perceived as "a trip planner with a council link."** Lead the pitch with the persona audit and process layer.

## Research findings (checked Nov 12, 2026)

**Toronto open data (CKAN API works, Open Government Licence – Toronto)**
- *Voting Record* (2022-2026 resource, 46,815 rows, updated 2026-11-07): columns Term, First/Last Name, Committee, Date/Time, Agenda Item #, Agenda Item Title, Motion Type, Vote, Result, Vote Description. Item numbers look like `2026.TE34.104`. Motion types include Adopt Item, Adopt Item as Amended, Amend Item, Amend Item (Additional), Defer Item, Refer Item. It includes Community Councils, committees and Toronto Transit Commission votes. The datastore API returns at most 32,000 rows per call; page with `offset`. The 2022-2026 term file is the outgoing council; a new-term file may not exist yet.
- *Report Request Log* (2022-2026, XLSX only, updated 2026-08-26): Status, Req. Body, Meeting Date, Item Number, Agenda title, Directive, Rpt to, Report Back Timing, Assigned to, Closed by, Date for Order. It links requests to report-back items. Not every decision appears.
- *Merged GTFS – TTC* (monthly): feed valid 2026-11-01 to 2026-12-19. `stops.txt` has `wheelchair_boarding` (of 9,462 stops/platforms: 8,115 accessible, 1,347 not accessible; the 368 "unknown" values sit on other node types); `trips.txt` has `wheelchair_accessible`; `pathways.txt` and `levels.txt` describe station paths. **Only the current network is published, so before/after for a proposed change needs an archived or separately obtained feed (unresolved).**
- *Pedestrian Network* (updated 2026-02): the City warns it has "known limitations in completeness and classifications". *Sidewalk Inventory* is from 2015 aerial imagery (last updated 2019). Both are usable for presence of sidewalks, not condition. *Sidewalk Construction Program*, *Road Resurfacing/Reconstruction Program* and *311 Service Requests* are updated recently and may help with construction and complaint history.

**Official item pages**
- `secure.toronto.ca/council/agenda-item.do?item=...` returns HTTP 403 to plain scripted requests (curl) but loads in a real browser. A pilot would need a Clerk feed or agreement, or a browser-based fetcher. Item pages show tracking status, decision text, status (e.g. Amended), wards, background reports, public communications (with names), motions and recorded votes.
- Staff reports are PDFs under `toronto.ca/legdocs/mmis/...`. A tagged PDF extracted cleanly with a text library (no OCR needed). Large attachments (152 pages, 15.7 MB) exceed simple fetch tools.

**Candidate demo items (all checked against the voting record; item pages for the first one only)**
1. `2026.TE34.104` – Initial Findings Report: Transit Priority Measures to Support the 505 Dundas 6-Minute Network. Went Community Council (Jul 8-9, 2026, adopted with amendments) then City Council (Jul 29-30, 2026, adopted as amended; vote 20 Yes). Wards 4, 9, 10, 13. Staff report dated Jun 19, 2026; public communications attached. Good for the explain layer and a status/amendment timeline; transit with a spatial footprint, though the decision itself requests further study.
2. `2026.IE31.8` – Pedestrian Access to Laneway Houses in Ward 11 During Snow Events (Infrastructure and Environment Committee, Jul 15, 2026). **Opened.** Status: Referred, not decided: the Committee referred it to the Deputy City Manager, Infrastructure Services, for a broader review of snow clearing for laneways with laneway housing, to report back under the decision on item IE29.1. The motion's summary says City staff declined (in 2026.IE29.1) to recommend snow removal for the 2,744 public laneways. Non-transit, winter and pedestrian access, one ward. Good for showing "referred is not decided."
3. `2026.TE32.25` then `2026.MM42.46` – Spadina Road (Lowther Ave to Kendal Ave), TTC subway ventilation equipment replacement staging area. **Both opened.** Council adopted TE32.25 on consent, without amendments and without debate (May 20-21, 2026): lane closures and left-turn/through prohibitions on Spadina Rd at Lowther Ave from Oct 1, 2026 to Dec 31, 2027. Council then re-opened it on Jun 24-25, 2026 (MM42.46, adopted without amendments) and deleted Parts 1 to 17, 19 and 27 of the earlier decision. The first decision was a by-law (530-2026); MM42.46 links by-laws 1126-2026 and 1127-2026. **Correction (after reading the documents):** MM42.46 did not reverse the decision. It replaced the single-phase plan with a revised two-phase one: work on the north shaft Mar 1 to Aug 30, 2027, then the south shaft Sep 1, 2027 to Feb 28, 2028, so the start moves from Oct 1, 2026 to Mar 1, 2027 and the staging areas shrink. The motion says staff offered this after the councillor asked them to reduce local impacts. Good example of "decided on consent, then revised" and of dated, location-specific closures and turn bans.
4. `2025 TTC Board – 2026 Annual Network Plan` (staff report dated Nov 3, 2025, to the TTC Board). Rich route-change content (Appendix 5 lists road segments with service added/removed) but **no matching vote found in the voting record** by title, so the decision outcome is unconfirmed.
5. Several zoning items (e.g. `2026.NY34.12`, `2026.TE34.21`) as a "near me" geography example if needed.

**Other findings**
- TTC service adjustments (July 26, Nov 1, etc.) are operational notices with no vote; the Board and Council do not decide every change.
- Item pages list public communications with names and emails: exclude or minimize, per the brief.

**Participation rules (official City page, checked Nov 12, 2026)**
- "Request to Speak" button on the agenda item. The page says to register by 12:00 p.m. the day before the meeting at the latest. A search snippet of another City-related page said 4:30 p.m., so the two sources disagreed: always read the deadline from the item page, never hard-code or infer it.
- "Submit Comments" button: no specific cutoff stated; late communications are not distributed, and comments after a decision are not accepted into the record.
- Presenters are generally not heard at City Council itself (only committees/boards, unless legislated). Names and comments become public record and may be indexed by search engines (a data-minimization point for any comment draft).
- Decided items (all the candidates above) no longer show an open window, so the "next date to act" logic has to be demoed on a still-open item or a clearly labelled simulated one.

**Archived transit schedules**
- Transitland lists 100+ archived versions of the TTC feed (feed id `f-dpz8-ttc`). Its API returned 401 Unauthorized without a key, and the archive's access terms have changed, so a free key and the current terms need checking before relying on it. Not yet downloaded. The feed's page lists recent versions with service date ranges. A candidate replay pair: `d4ca443e…` (fetched 2026-09-26, service 2026-09-30 to 2026-10-31) and `cbfed3e1…` (fetched 2026-10-26, service 2026-11-01 to 2026-12-21; the current one). Both show "available for download from the Feed Archive." Keyless download attempts returned 401/403. The Nov 1 change was an operational TTC adjustment (not a Council or Board vote), so it works as a replay of a real network change, not as a decision to explain.

## Decision: simulated before/after (Nov 12, 2026)
Transitland's sources disagree on whether a free key can download historical feeds (the plans page says historical feeds are not on the free plan, with a free-credits request form for non-commercial users; the API docs say the download endpoint needs a Professional or Enterprise key). Rather than depend on that, the demo uses a **clearly labelled simulated change**: take the current TTC feed and apply an edit to a few routes, anchored to a real item (for example the 505 Dundas transit priority measures) but not using that plan's real numbers. Label it as a simulation everywhere it appears. A municipality piloting this would get the old and proposed schedules directly from its transit agency. Optional upgrade: request the free historical-download credits and add a real replay.

## Research findings, round 2 (Nov 12, 2026)

**Staff reports read (PDFs extract cleanly)**
- *505 Dundas* (report dated Jun 19, 2026, to Toronto and East York Community Council): staff recommended only that the Community Council **receive the report for information**. The Council decision (a request to investigate expanding transit priority measures, report back Q1 2027) goes beyond the staff recommendation. This is a clean example of staff recommendation vs. committee vs. Council decision. The report reports before/after results with caveats: only one representative week (Apr 6-12, 2026) of post-implementation data, other routes diverting, CaféTO barriers affecting later data, ridership up about 20% but "cannot be solely attributed" to the measures. It also says 6-minute headways "began on November 15, 2026", which cannot be right in a report dated June 2026 (likely a typo for 2025). Quote as written and flag the inconsistency.
- *Laneway snow (IE31.8)*: the Councillor's motion asked for a report back at the first 2027 meeting on snow clearing for pedestrian access to laneway homes in Ward 11, starting with Shaftesbury Court and Croft Street. The Committee instead referred it for a broader review of laneways with laneway housing (financial implications included), reporting back under the decision on IE29.1 (the winter maintenance report, 38 pages). The origin is a member's letter, not a staff report.
- *Spadina Road*: staff report dated Apr 14, 2026 lists 11+ numbered recommendations (lane closures, turn and through-movement bans, rescinded parking rules) for Oct 1, 2026 to Dec 31, 2027. The follow-up motion text itself notes the area has had "TTC Easier Access construction for the last several years".
- *2026 Annual Network Plan*: a TTC executive update says the Board approved it in November 2025, including the Appendix 5 route changes. No matching row in the voting record by title (likely not recorded under that title), so the vote count is unconfirmed.

**A live item with an open window exists**
- Toronto Preservation Board, Nov 16, 2026, 9:30 AM, meeting `2027.PB1` (first of the new term; six items). Item pages (e.g. `2027.PB1.6`, 1337 Queen St W, demolition and a 16-storey tower in the Parkdale Main Street Heritage Conservation District, Ward 4; `2027.PB1.1`, 8 Arnold Ave, notice of intention to designate) show **Submit Comments** and **Request to Speak** buttons and the status "This item will be considered by ... on November 16, 2026." The page text shows no per-item deadline. Saved to `data/raw/live_snapshot.json`.
- The "Agenda Deadlines and Closing Dates" page lists agenda closing, distribution, motions-without-notice and bills deadlines for members and staff. It is **not** the public's speaking or comment deadline, which is a good reason never to infer one from a calendar.
- Quirk: meetings in the new term are numbered `2027.PB1...` although the meeting is in November 2026. Do not parse the calendar year from an item number.
- New term: 2026-2030 Council term starts Nov 15, 2026; first Council meeting Nov 18-19, 2026; a regular business meeting follows in December. I did not find the new committee calendar.

**More datasets**
- Open data has *Street Furniture – Transit Shelter* and *Street Furniture – Bench* (updated 2026), so shelter and seating at stops can be checked. No curb-ramp or tactile-paving dataset was found in the catalogue. No snow or winter-maintenance dataset was found; use the winter maintenance report (IE29.1), 311 data, and the sidewalk and road construction programs instead.

**Routing**
- OpenTripPlanner supports wheelchair routing using `wheelchair_boarding` (stops) and `wheelchair_accessible` (trips). Its docs (2.2) give a wheelchair `maxSlope` default of 8.3% and say incline comes from separately configured elevation data, not OSM. A thread suggests unknown accessibility values are not treated as inaccessible; confirm against current docs. Java 25 is installed locally.

**Imagery**
- Mapillary imagery is generally CC BY-SA 4.0 (attribution and share-alike). Its own terms may add conditions, so check current terms before any automated analysis. Toronto coverage and curb-ramp detection accuracy not checked.

**Prior art**
- WMATA's comparison tool lets riders compare current routes with the proposed network, leave route-specific comments, and has a screen-readable sidebar. Whether it reports walking distance or supports mobility personas is not confirmed.

**Winter maintenance facts (from the 38-page 2025-2026 Annual Winter Maintenance Report, item IE29.1; for audit-agent evidence)**
- The City begins sidewalk clearing once snow accumulation reaches 2 cm, and crews typically complete a full clearing cycle in about 12 hours after that.
- Public laneways (2,744, about 334 km) get salting only, within a stated window; **no plowing**. The report says this matches practice elsewhere in Ontario.
- 311 requests for "Sidewalk Snow Clearing" rose from 11,611 (2024-25) to 14,403 (2025-26); "Sidewalk Icy, Needs Sand/Salt" from 1,938 to 3,020; "Driveway Blocked by Windrow" from 4,049 to 8,713 (top-five table, Attachment 3).
- Before the 2025-26 winter the TTC gave the City a list of priority stops and routes, and stop access was cleared by a mix of machines and hand crews.
- Treat these as service-level and complaint-volume evidence, not a measure of whether a given sidewalk was clear on a given day.

## To verify (still open)
- [ ] (Optional) A real before/after schedule pair (Transitland free credits). Demo uses a labelled simulation.
- [ ] OTP wheelchair behaviour and defaults against current docs; elevation data source for Toronto.
- [ ] Whether the open item pages show any deadline text when the meeting is nearer (the Nov 16 items show none).
- [ ] The TTC Board vote on the 2026 Annual Network Plan (in the Board minutes rather than the voting record).
- [ ] Curb-ramp and tactile-paving data (none found).
- [ ] Mapillary terms and Toronto coverage.

## Build status (Nov 12, 2026)
Scaffolded and running (Python 3.14, FastAPI, Jinja2, server-rendered, no JavaScript needed):
- `data/raw/*_snapshot.json`: saved copies of official item pages (11 items: 5 decided/referred, 6 upcoming Preservation Board items), fetched with a real browser because plain scripted requests get HTTP 403.
- `triplens/parse_item.py`: stages (body, date, status, wards), official wording copied verbatim, motions, vote totals, background documents, by-laws, upcoming flag, and the participation buttons seen on the page (Request to Speak / Submit Comments). Public communications are kept as counts and dates only.
- `triplens/parse_report.py` + `scripts/build_reports.py`: downloads linked staff reports and member letters (skips files over 12 MB or 80 pages), extracts header, Summary, Recommendations, Financial impact and Decision history verbatim with page numbers.
- `triplens/verify.py`: every extracted fact must appear in the PDF text (whitespace-insensitive) or it is dropped. No AI is used anywhere yet, so there is nothing to hallucinate; an AI plain-language rewriter would have to pass the same check.
- `triplens/app.py` + templates: index (coming up / decided), item page with status, wards, "can you still have a say" (shows the buttons the official page lists, never a deadline), recommended vs decided side by side, report excerpts with page numbers, process timeline, caveats, sources. Plain-language status labels are a fixed lookup table.
- Tests: 12 pass (verbatim checks, no names of letter writers, Dundas staff recommendation differs from the decision, upcoming items have no invented deadline).

Run: `scripts/build_items.py`, then `scripts/build_reports.py`, then `.venv/bin/uvicorn triplens.app:app --port 8765` and open http://127.0.0.1:8765

Not built yet: address parsing and geocoding, the trip lens, audit agents, the staff view, translation, a "load a new item" flow for a clerk.

## AI plain-language layer (added Nov 12, 2026)
- `triplens/rewrite.py` + `scripts/build_plain.py`: Claude (`claude-opus-5-5`, effort medium, structured output, server-side refusal fallback enabled) rewrites each Summary, Recommendation and Decision passage into 2 to 6 short sentences. Each sentence must carry an exact quote from the source. Software drops a sentence if (a) the quote is not in the source, (b) it contains a number, date or amount not in the source, or (c) it uses stronger wording than the quote ("must", "will", "only", "required", "all" and similar), which stops a "request" or "recommendation" turning into an obligation. Dropped sentences are stored with the reason.
- Results are stored in `data/plain/` and shown on the item page in a labelled "Written by AI, then checked by software" box with the supporting quotes one click away. Long passages (over 4,000 characters, or more than 8 numbered parts) carry a warning that the sentences cover the main points only.
- `data/notes/*.json`: hand-written notes about known problems in a source document (e.g. the Dundas report's impossible "November 15, 2026" date), shown under "What this page can't tell you".
- The API key lives in `.env` (gitignored, mode 600). Run `scripts/build_plain.py` after `build_items.py` and `build_reports.py`.
- Limits: the checks catch invented quotes, numbers and strengthened wording. They do not catch every omission or misleading emphasis, which is why long passages are flagged and the official wording is always shown. A rewrite is stale if the official text changes; a test compares stored sources to the current text. Human review of the rewrites for the demo items is still needed before submission.
- Tests: 23 pass.

## Rider access and audit agents (added Nov 12-13, 2026)
- `scripts/build_access_data.py`: builds `data/geo/stops.json` from the TTC GTFS feed (base weekday, Saturday, Sunday patterns only) and the City's shelter and bench datasets. For each stop: wheelchair boarding flag, trip accessibility flags (accessible / not accessible / no information), shelter and bench listed, routes, first and last departures and departures per hour.
- `scripts/build_locations.py`: places demo items on the map from the City's Address Points dataset or a clearly labelled representative point (`data/locations.json`).
- `triplens/access.py`: three illustrative rider personas (wheelchair user 400 m, senior with a cane or walker 250 m, shift worker 600 m walking limits; straight-line distance times 1.3) and fixed rules that raise "barrier" or "worth knowing" flags. For a wheelchair user a stop only counts if boarding is listed as possible and some trips are flagged accessible.
- `triplens/agents.py` + `scripts/run_audits.py`: three Claude agents (stops and boarding, walking and winter, service and schedule) per place and rider, using five local tools (nearby stops, stop detail, planned road and sidewalk works, exact winter-service sentences from the City's winter maintenance report). Findings are kept only if they cite exact tool text and their numbers match. Agents cannot assign a barrier label. `scripts/consolidate_audits.py` groups duplicate findings (groups only, no new text).
- Pages: `/access/<location id>?persona=...`, linked from each item that has a location.
- Cost of the first run: 15 audits (5 places x 3 riders, 3 agents each) used roughly 20,000 to 36,000 input and 4,000 to 5,000 output tokens each, about $0.16 to $0.23 per audit at list prices, about $2.80 in all, plus a small consolidation pass.
- Data finding: in the TTC feed every streetcar trip is flagged `wheelchair_accessible = 2` (not accessible) while bus and subway trips are flagged 1. A stop can therefore list boarding as possible while all its trips are flagged not accessible. The feed does not explain this; the page says so and tells readers to check the TTC.
- Tests: 32 pass.

Run order: `build_items.py`, `build_reports.py`, `build_plain.py`, `build_access_data.py`, `build_locations.py`, `run_audits.py`, `consolidate_audits.py`, then `uvicorn triplens.app:app --port 8765`.

## Deliverable drafts
- `docs/readiness-report-draft.md`: text for the organizers' one-page Word template (word limits checked).
- `docs/architecture.md`: requirements traced to the brief, architecture diagrams, design rationale, verification table, limits.
- `docs/ai-use-log.md`: how AI was used and checked (has checkboxes for your own review).

## Route check (added Nov 13, 2026)
The resident enters the trip they make (start, destination, bus/streetcar/subway route, rider, day and time of day). The tool shows what the open data lists along it. No routing, timing or recommendations.
- Pages: `/route` (form), `/route/stops` (choose stops), `/route/result`, and examples at `/route/example/<key>`.
- Modules: `triplens/geocode.py` (local address lookup), `trip.py` (real route line between chosen stops, straight-line walks), `exposure.py` (decisions within 150 m, works within 120 m, decisions that name the route, fixed rider rules), `svgmap.py` (tile-free drawing), `labels.py`.
- Data builds: `scripts/build_route_data.py` (GTFS shapes and ordered stops into `data/geo/routes.json`) and `scripts/build_address_index.py` (City Address Points CSV into `data/geo/address.sqlite`). Download the CSV first: Toronto Open Data, "Address Points (Municipal) - Toronto One Address Repository", file "Address Points - 4326.csv", saved as `data/geo/address_points.csv` (about 180 MB, not committed).
- Privacy: addresses are looked up locally, nothing is stored, no cookies, no map tiles, addresses are not in URLs. A test checks that no file is written.
- Design doc: `docs/route-check-architecture.md`.
- Tests: 42 pass.
- Not done: AI-written reports for example trips (the route check uses fixed rules only), transfers beyond two routes, the return trip, translation.
Run order now also includes: `build_access_data.py`, `build_route_data.py`, `build_address_index.py`.

## Before and after a change (added Nov 13, 2026)
Changes live in `data/changes/*.json` as structured effects with exact quotes from saved source text (`data/raw/ttc_512_stclair.txt`). `triplens/changes.py` applies them to the resident's trip and reruns the rider rules, then the result page shows a before/after table and new accessibility issues.
- Real: TTC proposal to remove nine 512 St Clair stops (status: proposed; stops still in the Nov 2026 schedule file). Example: `/route/example/stclair-512`.
- Simulated (labelled): shelter and bench removal at two 501 Queen stops, shown on `/route/example/queen-beverley`.
- Tests: 47 pass.
