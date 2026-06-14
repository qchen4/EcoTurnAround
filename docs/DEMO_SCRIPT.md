# EcoTurnaround OS — 3-Minute Live Demo Script

**Setup before you start:** `streamlit run app.py` open on the **Decision
Cockpit** tab, default goal prompt loaded, browser maximized. Everything is a
synthetic ATL-sandbox prototype — say so once, early.

---

## 0:00–0:30 — Problem

> "Airports are electrifying their ground fleets — baggage tractors, belt
> loaders, tow tractors, catering trucks. During that transition, diesel, EV,
> and future autonomous vehicles all coexist, sharing chargers and restricted
> airside zones. Operations teams have to cut emissions and waste **without**
> missing aircraft turnarounds or crossing safety boundaries. Today that
> tradeoff is mostly manual guesswork."

## 0:30–1:00 — Solution

> "EcoTurnaround OS is an ATL-sandbox **decision cockpit**. You type a goal in
> plain English. It builds an airport scenario, runs a baseline dispatch and an
> optimized dispatch, checks hard safety constraints, generates an
> engineering-style bottleneck report, proposes refinements, and remembers the
> lessons for next time. To be clear: this is synthetic prototype data — no real
> Delta or ATL numbers, and we don't claim global optimality."

## 1:00–2:15 — Live demo

1. **(1:00)** "Here's the goal: reduce ground-ops emissions without sacrificing
   turnaround reliability, and keep safety boundaries hard." Click **Run Full
   Pipeline**.
2. **(1:15)** Point at KPI cards: "**CO2e index drops to ~31** and **cost to
   ~83** versus a baseline of 100 — lower is better. **Late-task rate is
   preserved** — we didn't trade reliability for emissions. **Verifier: PASS** —
   no hard constraints broken."
3. **(1:35)** Read the tradeoff line: "It's honest about the cost: emissions and
   cost improve, lateness holds, **but perishable waste risk goes up**."
4. **(1:50)** Open **Bottleneck Report**: "This is the *why* — like a timing
   report. The worst-waste finding shows a catering task with high freshness
   risk and elapsed time, with evidence and a confidence score."
5. **(2:05)** Open **Refinement & Memory**: "The system proposes increasing
   **freshness priority** and pre-staging a catering vehicle — automatically.
   But anything touching **minimum SOC, restricted runway crossings,
   autonomous corridors, or critical deadlines stays HUMAN-GATED** — never
   auto-relaxed."

## 2:15–2:45 — Impact and trust

> "So the impact story is: measurable emissions and cost reductions on
> synthetic data, with reliability preserved and **every** safety boundary
> protected. The trust story is the verifier plus the human gate — the AI tunes
> objectives, humans own safety. And it learns: clicking **Save Reflection**
> writes a Hermes memory entry — failure modes and lessons — that future runs
> retrieve."

## 2:45–3:00 — Close

> "EcoTurnaround OS turns a sentence into a verifiable, explainable, and
> safety-bounded ground-ops plan — and gets smarter every run. That's how we'd
> help airlines decarbonize ground operations without risking a single
> turnaround. Thank you."

---

### Backup talking points (if asked / if time)

- **Artifacts tab**: one-click export of scenario, schedules, metrics,
  bottleneck report, proposals, and reflection entry for audit.
- **Determinism**: same seed + goal → identical results, so the demo never
  surprises you live.
- **Why waste rose**: the optimizer prefers clean electric vehicles, which can
  add small pickup delays for perishables — exactly what the refinement step
  then corrects.
