# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: Toronto transit riders with accessibility needs, checking how City council decisions changed the bus or streetcar trip they take every day. The three riders the tool models are a wheelchair user (400 m walking limit), a senior using a cane or walker (250 m), and a shift worker travelling late at night or early in the morning (600 m). These limits are illustrative, not medical or legal definitions.

Secondary (they must be able to use it unaided, but design decisions favour the primary riders): hackathon judges and municipal staff for CIVIC Hack 2026, Challenge 1 "Making municipal decisions easier to understand".

## Product Purpose

TripLens shows a resident what a municipal decision did, or would do, to their own trip. They pick a start, a destination, a route and their own stops. TripLens then shows the trip before and after each relevant decision, lists new accessibility issues and the ones a decision removes, adds ground evidence (City 311 requests and rider reports near their stops and walks), and helps them write a report they can send to their councillor, 311 or the TTC.

Success: a rider understands in plain words what changed for them, can see where each fact came from, and knows where to have a say.

## Positioning

Checked facts. Every claim is one of three things: copied word for word from an official source with its page number, computed by fixed rules from open data, or written by AI and shown only when software confirms its quote is on the cited page, with no new numbers and no stronger wording. Trip planners and agency "compare my trip" tools do not tie a council decision's own text to one rider's trip this way.

## Operating Context

- Riders use it on a laptop or phone, at home, before or after a trip. Many have low vision, limited mobility, or limited time.
- Sources: City of Toronto council and committee items and staff reports (legdocs PDFs, page numbered), TTC GTFS schedule, City Pedestrian Network, Address Points, transit shelters and benches, 311 service requests.
- Routes: `/` landing page, `/map` (3D map trip check), `/route` (text-only trip check), `/decisions` (council items), `/item/<id>`, `/access/<loc>`, `/research/<route>`.

## Capabilities and Constraints

- FastAPI + Jinja server-rendered pages; the map uses MapLibre with OpenFreeMap tiles. Python 3.14 in `.venv`.
- Change files in `data/changes/` (real decisions with verified quotes; simulations always labelled "Simulation").
- Free full-text search over City staff reports; an optional live research agent (Claude) whose findings pass a quote checker. AI never runs unless a user presses the button.
- No accounts, cookies, analytics, or stored addresses. Rider reports store only category, rounded location, stop id and date.
- The tool does not plan trips, suggest stops, recommend, take sides, or call a trip "safe" or "possible".
- Hackathon deadline: Saturday Nov 14, 2026, 10:00 am ET. No edits after.

## Brand Commitments

- Name: TripLens (working name; the owner may rename it).
- Voice: warm and plain. Encouraging, simple words a child or a senior can follow. Never alarming, never partisan, never advice. Estimates are labelled as estimates; what was not checked is said.
- Wording reserved for fixed rules only: "limit" and "barrier". Never "safe", "accessible route", or deadlines the source does not state.
- Not an official City of Toronto or TTC service; no City or TTC logos or branding.

## Evidence on Hand

- Real decisions with quotes: TTC 512 St Clair stop removals (proposed); RapidTO 7 Bathurst and 29 Dufferin stop removals (item 2025.EX25.4, implemented); Harbord bikeway stop shifts and bus/bike platforms (item 2024.IE10.2); Front St W lay-by shelter (item 2025.EX21.4).
- Computed figures, e.g. 7 Bathurst for a senior with a walker: walk to the stop about 62 m before, about 419 m after (`triplens/landing.py`).
- 1,033 indexed staff reports from 401 items; 12,834 located 311 requests for 2026.
- Openly licensed photographs with credits in `triplens/static/img/credits.json`.
- No testimonials, users, partners, endorsements or usage numbers exist. Do not invent any.

## Product Principles

1. Every claim traces to its source, visibly and in one click.
2. One trip, one rider: show the decision as it lands on a specific person, before and after.
3. Plain and kind: the words should be understandable by a child and respectful to a senior.
4. Lead to a say, never to advice: show where to send a report, and let the person write their own view.
5. Honest gaps: simulations, reconstructions, estimates and unchecked leads are always labelled.

## Accessibility & Inclusion

The primary users have accessibility needs, so WCAG 2.2 AA is the floor: 4.5:1 text contrast, full keyboard use, visible focus, labelled controls, text equivalents for the map and drawings, 44px touch targets, works at phone width and 200% zoom, and respects reduced motion.
