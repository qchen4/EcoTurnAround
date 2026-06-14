# EcoTurnaround OS — Screenshot Guide (for Devpost)

Capture order matches the demo flow. Run `streamlit run app.py`, click **Run
Full Pipeline** with the default goal and seed 42 first, then capture. Use a
maximized, light-theme browser window. Keep the synthetic ATL-sandbox
disclaimer visible in at least the first shot.

---

## 1. Decision Cockpit with KPI cards

**File suggestion:** `01_decision_cockpit.png`

**Show:** the hero title/subtitle, the synthetic disclaimer, the track-alignment
line, the natural-language goal, and the KPI cards after a run (CO2e ~31, Cost
~83, Waste ~106, Late Task Rate, Verifier = PASS), plus the tradeoff line and
top recommendation.

**Demonstrates:** the whole value prop in one frame — plain-English goal in,
measurable improvements out, reliability preserved, safety verified, with an
honest tradeoff summary.

## 2. Schedule Comparison

**File suggestion:** `02_schedule_comparison.png`

**Show:** the baseline-vs-optimized metrics table and the per-index metric cards
(baseline = 100, lower is better), plus the baseline vs optimized late-rate
comparison.

**Demonstrates:** rigorous, transparent before/after measurement — emissions and
cost fall while lateness is preserved — not a black-box claim.

## 3. Bottleneck Report

**File suggestion:** `03_bottleneck_report.png`

**Show:** the expanded `worst_freshness_waste_event` (or `worst_co2e_event`)
finding with its human-readable summary, severity, confidence bar, likely cause,
suggested what-if, and the raw evidence JSON expander.

**Demonstrates:** engineering-grade explainability — a Vivado-timing-report-style
diagnosis of *why* a metric regressed, with evidence and confidence.

## 4. Refinement & Memory

**File suggestion:** `04_refinement_memory.png`

**Show:** the refinement proposal cards clearly labeled **AUTO** vs **HUMAN
GATE**, the Lesson summary (failure modes, next steps, do-not-auto-relax items),
and the retrieved relevant lessons block (after saving at least one reflection).

**Demonstrates:** the safety-gated adaptive loop and Hermes memory — AI tunes
objectives, humans own safety boundaries, and the system learns across runs.

## 5. Artifacts page

**File suggestion:** `05_artifacts.png`

**Show:** the grid of download buttons (scenario JSON, baseline/optimized
schedule CSV, baseline/optimized metrics JSON, bottleneck report JSON,
refinement proposals JSON, reflection entry JSON).

**Demonstrates:** auditability and reproducibility — every artifact of a run is
exportable for inspection or downstream use.

---

### Optional extra shots

- **Scenario & Model** tab: fleet-by-powertrain, tasks-by-type, charger-by-type,
  and the ATL-sandbox zone list — useful to prove the synthetic model is rich.
- **Sidebar**: shows version, disclaimer, and track alignment in every view.
