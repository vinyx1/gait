# Devpost description (draft) and demo video script

## Devpost description

**Problem.** Council and transit decisions decide whether people can get around, but they are buried in long reports and comment windows are easy to miss. People with accessibility needs (wheelchair users and people who use a cane or walker) often learn what a change means for them only after it happens: a stop disappears, a shelter goes, the walk gets longer.

**Who it's for.** Residents who depend on public transit and have accessibility needs, and the clerks and councillors' staff who explain decisions to them.

**What we built.** Gait:
- **Check my route:** enter where you start, where you go, the bus or streetcar you take and the stops you use. Gait shows what the open data lists along your trip: decisions nearby (and whether you can still comment), planned works, and how your stops work for your kind of rider.
- **Before and after a change:** when a change affects your route, Gait applies it to your trip and shows what is different and which new accessibility issues appear. Real example: City Council approved road and sidewalk closures to build the Ontario Line's Cosburn Station. For someone who uses a cane or walker starting on Cosburn Avenue, the walk to the 72 Pape stop goes from about 118 m to about 288 m.
- **Plain-language decisions:** each council item shows its status, staff recommendation next to the decision, exact source quotes with page numbers, and AI-written summaries that software checks against the source (a sentence is dropped if its quote, numbers or wording strength do not match).

**How we kept it accurate and fair.** Official wording is copied, not paraphrased. AI output is shown only if it passes checks. Only fixed rules can mark a "limit". Deadlines are never guessed. Addresses never leave the computer and nothing is stored. Simulations are labelled.

**What's next.** Load every agenda item through a feed from the City Clerk, draft change effects from reports with AI (still checked against quotes), test with accessibility groups, and add translation.

**Built with.** Python, FastAPI, Jinja2, pypdf, the Anthropic API (Claude) for checked rewrites and audit agents, Claude Code for development, City of Toronto Open Data, the TTC GTFS feed.

## Video script (target 2:40, hard limit 3:00)

| Time | Screen | Say |
|---|---|---|
| 0:00 to 0:20 | Title page | "When a city removes a bus stop or a shelter, people with mobility needs feel it first and hear about it last. Gait shows what a decision means for your own trip, before it happens." |
| 0:20 to 0:50 | `/map`, then the Cosburn example | "I set where I start, where I go, the 72 Pape, and the stops I use. I pick 'person using a cane or walker'." |
| 0:50 to 1:30 | Before and after box | "City Council approved closures to build the Ontario Line's Cosburn Station. The sidewalk is closed and my stop has moved. My walk goes from about 118 metres to about 288, over the limit we assume for this rider. Every line links to the City's own report, and Gait finds each quote again on its page." |
| 1:30 to 1:55 | Queen example: simulation box and open decisions | "Here, a labelled simulation removes shelters. And two heritage decisions near this trip are still open: the page shows the City's Request to Speak and Submit Comments buttons. We never guess a deadline." |
| 1:55 to 2:25 | An item page: recommended vs decided, AI box, quotes | "Each decision shows what staff recommended next to what Council decided. The plain-language summary is written by AI, but software keeps a sentence only if its quote and numbers match the source." |
| 2:25 to 2:45 | Limits section | "We say what we didn't check: real sidewalks, snow, and the TTC file that flags every streetcar trip as not accessible without explaining why." |
| 2:45 to 2:55 | Title | "Your route, your rider, before the vote. Gait." |

Record at 1280 px width, zoom 125 percent, and rehearse once with a timer.
