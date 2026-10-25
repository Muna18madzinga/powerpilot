# PowerPilot pilot plan

A 90-day pilot on 30 NetOne base stations in the Midlands, run with the MSU Innovation Hub and Ubuntu Software Labs.

## The problem it targets

Load-shedding leaves sites on batteries and generators for most of the day. Sites go dark when a battery runs flat
before the grid returns, when a tank runs dry between refuel rounds, or when batteries and diesel are stolen.
Each of these is visible in telemetry hours before customers lose signal, but today it is acted on only after a
site is reported down.

## What NetOne provides

| Data | Used for | Access |
|---|---|---|
| NOC alarm history, 6 months | training the outage-risk model | export, read-only |
| Rectifier and battery readings per site | battery charge and health | read-only feed |
| Generator run and fuel-level readings | fuel forecast and theft detection | read-only feed |
| ZESA load-shedding schedule and zone per site | outage windows | published schedule |
| Refuel and maintenance records | baseline cost and crew distance | export |

No control access is needed. All data stays on NetOne servers.

## Timeline

| Weeks | Stage | What happens |
|---|---|---|
| 1–2 | Connect | Map the 30 sites, load history, check data quality |
| 3–6 | Shadow | PowerPilot runs alongside the NOC. Its predictions are logged and compared with what actually happened |
| 7–12 | Assist | Engineers receive recommendations and approve or dismiss them. Cell sleep and generator scheduling run on agreed sites |
| 13 | Review | Joint report against the scorecard below |

## Scorecard, agreed before the pilot starts

- Site outage hours against the same sites in the 90 days before the pilot
- Diesel litres burned per site per day
- Diesel and battery losses from theft
- Mean time to restore a site
- Crew kilometres driven
- Share of outages that PowerPilot predicted at least two hours ahead

## Commercial structure

- No cost to NetOne for the pilot, under a memorandum of understanding with the MSU Innovation Hub
- If the scorecard targets are met, a licence or a share of verified savings for the roll-out
- Built, hosted and supported locally in Zimbabwe

## Risks and how they are handled

| Risk | Mitigation |
|---|---|
| Telemetry gaps or noisy sensors | Shadow phase measures data quality first. Models were built to tolerate sensor noise |
| Wrong recommendation | Every field action needs an engineer’s approval during the pilot |
| Radio changes affecting customers | Cell sleep wakes automatically above a traffic threshold and is limited to agreed sites |
| Data security | Read-only access, on-premises deployment, no customer records used |
