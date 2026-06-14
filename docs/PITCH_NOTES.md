# EcoTurnaround OS — Pitch Notes

## One-sentence pitch

EcoTurnaround OS turns a plain-English sustainability goal into a verifiable,
safety-bounded airport ground-ops dispatch plan — and remembers what it learns.

## 30-second pitch

Airports are electrifying their ground fleets, but diesel, EV, and autonomous
vehicles have to coexist while sharing chargers and avoiding restricted zones —
all without missing turnarounds. EcoTurnaround OS is an ATL-sandbox decision
cockpit: you type a goal, and it generates a scenario, runs baseline and
optimized dispatch, verifies hard safety constraints, explains the bottlenecks,
proposes refinements, and stores the lessons. It's synthetic prototype data,
but it shows the full decision loop end to end.

## 90-second pitch

Ground-service equipment is a real and growing source of airport emissions, and
the diesel-to-electric-to-autonomous transition makes dispatch genuinely hard:
mixed fleets, charging congestion, restricted airside corridors, and hard
turnaround deadlines. Most tools either optimize a black box or just chat.

EcoTurnaround OS does something different. You give it a goal in natural
language. It builds a synthetic ATL-sandbox airport, runs a weak baseline
dispatch and a smarter optimized dispatch, and shows before/after KPIs where the
baseline is normalized to 100 and lower is better. On our default scenario,
emissions and cost drop sharply while the late-task rate is preserved.

Crucially, it's **verifiable and honest**: a rule-based verifier confirms no
hard safety constraint is broken, and a bottleneck report — styled like an
engineering timing report — explains *why* perishable waste went up. The
refinement engine then proposes auto-tunable fixes like raising freshness
priority, while keeping anything safety-critical — minimum SOC, restricted
crossings, autonomous corridors, critical deadlines — behind a human gate.
Finally, Hermes memory records failure modes and lessons, so the next run starts
smarter. AI tunes objectives; humans own safety; the system learns.

## Three strongest judging points

- **Impact:** Targets a real decarbonization problem (airport GSE) and shows
  measurable emissions/cost reduction with reliability preserved — directly on
  the Port & Airport Sustainability and EV Charging Experience track.
- **Innovation:** Natural-language goal → *verifiable* model, an engineering-grade
  bottleneck/critical-path report, a safety-gated refinement loop, and Hermes
  reflection memory that makes optimization iterative.
- **Value / Polish:** One-click, fully offline, deterministic Streamlit cockpit
  with before/after KPIs, explanations, downloadable artifacts, and 135 passing
  tests — demo-ready without live debugging.

## Expected judge questions & answers

**1. Is this real ATL/Delta data?**
No. It's a synthetic ATL-sandbox: an ATL-*inspired* layout for storytelling. No
real Delta fleet counts, flight schedules, GSE locations, or charging data are
used.

**2. Is this globally optimal?**
No, and we don't claim it. The optimizer is a deterministic priority-based
rolling-horizon greedy policy — strong enough to clearly beat the baseline,
intentionally not a global MILP/VRP solver.

**3. Why airport ground operations?**
It's a concrete, high-impact decarbonization frontier where mixed-generation
fleets, charging, safety corridors, and hard deadlines collide — exactly the
kind of constrained tradeoff this tool makes legible.

**4. What makes this different from a chatbot?**
A chatbot gives an opinion; we produce a *checked* plan. Every run yields a
schedule, verifiable constraints, quantified KPIs, an evidence-backed bottleneck
report, and exportable artifacts.

**5. How do you keep AI from changing safety constraints?**
By design: the refinement engine separates auto-tunable objectives (emissions,
cost, lateness, freshness weights) from safety boundaries (minimum SOC,
restricted zones, autonomous corridors, critical deadlines), which are always
`human_gate` and never auto-relaxed. The verifier independently flags any
breach.

**6. What would you do with real data?**
Calibrate travel times, energy, and emissions to measured values; add real
charger contention; parse real goals via an LLM; and validate the optimizer
against historical schedules — all behind the same safety gate.

**7. Why does waste get worse in the optimized run?**
Because the optimizer prefers clean electric vehicles and shorter routes, which
can slightly delay perishable (catering) pickups. We surface this honestly: the
bottleneck report diagnoses it, and the refinement engine proposes raising
freshness priority and pre-staging a catering vehicle to fix it.
