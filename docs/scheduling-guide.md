# Construction Schedule Scheduling Guide

Wind power, solar, and infrastructure construction scheduling best practices for P6 CPM networks.

## 1. Contract Milestone Extraction

Extract all hard milestone dates from bidding documents and add them as `CS_MSO` constraints. Typical wind power project milestones:

| Milestone | Typical Requirement |
|-----------|-------------------|
| Start of Construction | N days after contract signing |
| First Foundation Pour | 30-45 days after start |
| First Turbine Hoisting | ~90 days after start |
| All Turbines Hoisted | 8-10 months after start |
| First Grid Connection | 5 days after all hoisted |
| All Grid Connected | 25 days after first grid |
| Completion | 60-70 days after all grid |

**Penalties are typically severe**: 0.5%/day per milestone delay, 0.3%/day for total duration overrun.

## 2. Foundation Engineering

**3 simultaneous work faces** (common contract requirement):
- Divide into 3 groups with SS+5 stagger (5-day interval between adjacent foundations)
- Each group's first foundation starts from the Start milestone via FS+0
- Bored pile foundations: 41-53 days/unit; Natural ground: 21-29 days/unit

Example (12 turbines, 3 groups):
```
Group 1 (4 turbines): WT03 → WT05 → WT08 → WT01
  WT03_F: A1000 FS+0
  WT05_F: WT03_F SS+5
  WT08_F: WT05_F SS+5
  ...

Group 2 (4 turbines): WT02 → WT04 → WT06 → WT07
  WT02_F: A1000 FS+0
  WT04_F: WT02_F SS+5
  ...

Group 3 (4 turbines): WT09 → WT10 → WT11 → WT12
  WT09_F: A1000 FS+0
  WT10_F: WT09_F SS+5
  ...
```

## 3. Road Engineering

- Construct in sections, SS+3 stagger (3 work faces)
- Roads are prerequisite for hoisting (hoisting platform acceptance depends on road completion)
- New roads: ~7-11 days/km; Renovation: ~3-4 days/km

## 4. Dual-Crane Parallel Hoisting

**Bidding documents typically require ≥2 main cranes operating simultaneously:**

```
Crane 1# (A4110) → Platform Verification 1# (A4131) → Hoisting Chain 1 (8 turbines)
Crane 2# (A4115) → Platform Verification 2# (A4132) → Hoisting Chain 2 (4 turbines)

A4131 depends on: A4110 FS+0 + Road(Section 2) FS+0
A4132 depends on: A4115 FS+0 + Road(Section 1) FS+0
```

Hoisting parameters:
- Single turbine hoisting: 11 days (including relocation preparation)
- Gap between consecutive hoists: FS+5 days (large crawler crane relocation)
- First hoisting foundation curing: FS+14 (fast track) or FS+30 (standard)
- A4000 (All Hoisting Complete) = max(Chain 1 last, Chain 2 last)

**Platform verification depends on the OPPOSITE crane's road section**, not its own. This is because Crane 1 needs to travel through Section 2 roads to reach its turbines, and vice versa.

**Curing constraint**: Each hoisting task has TWO predecessors:
1. Previous hoisting in the chain: FS+5 (sequencing)
2. Foundation for that turbine: FS+30 (concrete curing)

P6 uses the later of the two dates.

## 5. Electrical Commissioning

Typical chain:
```
A5420 (First Energization): A4000 FS+N, A5220 FS+0
A5415 (First Grid Milestone): A5420 FS+25
A5430 (All Grid Commissioning): A5415 FS+1, 25 days
A5900 (All Grid Ready): max(A4000, A5430, XB_INST)
```

The FS+N value needs to be calculated backwards from the target grid connection date:
```
N ≈ (Target A5415 date - A4000 date - A5420 duration - FS+25 total offset)
```
P6 has ~1 day offset; iterate and adjust N as needed.

## 6. Acceptance Engineering

```
A6110 (Defect Remediation): A5900 FS+0, 26 days
A6120 (As-built Docs): A5900 FS+0, 56 days
A6130 (Special Inspections): A6110 SS+5, 45 days
A6140 (Final Acceptance): max(A6120, A6130) FS+0, 10 days
A6150 (Handover): A6140 FS+0, 5 days
A6000 (Completion Date): A6150 FS+0
```

## 7. Commissioning-Completion Gap Adjustment

If the completion date is too early or too late, adjust the FS gap between A4000→A5420:
- Completion N days late → FS gap minus N days
- Completion N days early → FS gap plus N days
- Re-import to P6 and verify after each adjustment

## 8. Milestone Glue Method

Every project phase must be bounded by milestones:

```
Phase Start Milestone (Milestone, 0 days)
  ├─ TaskA → FS from Phase Start
  ├─ TaskB → FS from Phase Start
  └─ TaskC → FS from TaskA
Phase End Milestone (Milestone, 0 days)
  → FS from TaskB
  → FS from TaskC
```

Cross-phase: Next phase's start milestone depends on previous phase's end milestone via FS+0.
