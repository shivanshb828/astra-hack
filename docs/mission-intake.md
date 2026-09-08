# Mission Intake

The front half of MissionPCB: turning what someone says about their product
into the structured constraints the engine can check.

This is the part that has no closed form, and it is where a language model is
not merely convenient but the only available method. A person says:

> It's a heart monitor patch. Sticks to your chest, you wear it for two weeks
> straight, showers and all. Sends data to a phone. Has to be thin enough that
> nobody notices it under a shirt.

Nothing in that paragraph is a number. Every constraint in it is real:

| What they said | What it means | Encoded as |
| --- | --- | --- |
| sticks to your chest | patient-contact surface | `skin_contact: true` on the electrodes |
| wear it for two weeks | prolonged contact, IEC 60601-1 applies | `skin_contact_clearance_mm: 15` |
| heart monitor | microvolt biosignal, needs a long lead vector | AFE `from_noisy_components: 15`; `lead_vector` rule at 35 mm |
| showers and all | sealed enclosure, no open connector | charge window with a gasket, `max_reach_mm` |
| sends data to a phone | BLE radio, antenna keep-out, RF separation | `keepout_zone_mm`, `min_distance_mm` |
| nobody notices it | thin | `interior_mm.height: 7`, `max_component_height_mm: 4` |
| two weeks of runtime | a cell large enough to matter | LiPo in the BOM, `thermal_runaway_risk` |

Extracting that table is judgment. Checking it afterwards is arithmetic. See
`constraint-engine-contract.md` for why that line matters and where it sits.

---

## What intake must produce

Two files, both consumed directly by the engine:

1. **A parts library** — `parts/<product>-parts.json`. Every component with its
   dimensions, behaviour flags, and required clearances.
2. **A layout** — `layouts/<product>-<variant>.json`. The enclosure, the board,
   the mission thresholds, the mission rules, and the product-specific
   `rationales`.

Full field reference is in `constraint-engine-contract.md`. What follows is
what intake specifically is responsible for getting right.

### Emit constraints, not placements

Intake decides *what must be true*. The solver decides *where things go*.

```bash
PYTHONPATH=src python3 -m constraint_engine solve \
    --parts parts/ecg-patch-parts.json \
    --layout layouts/ecg-patch-naive.json \
    --out layouts/ecg-patch-solved.json
```

A layout still needs starting positions because the file format requires them,
but they are a seed, not an answer. Put the parts anywhere legal and let the
solver move them. The one exception is `anchored: true`, for a part whose
position is genuinely fixed by something outside the model.

### Every threshold needs a reason attached

A number with no justification cannot be reviewed, argued with, or corrected.
Whenever intake sets a threshold it must also write the `rationales` entry that
explains it in the product's own terms:

```jsonc
"mission": { "skin_contact_clearance_mm": 15 },
"rationales": {
  "safety.skin_contact_temp":
    "IEC 60601-1 caps prolonged patient skin contact at 43 C. This patch is "
    "worn continuously for days against bare skin, so a dissipating part near "
    "a skin-contact surface is a burn exposure, and the local heating also "
    "drives electrode half-cell potential drift into the measurement."
}
```

The checker has generic fallback text for every rule family, but it is
deliberately bland physics. If the report reads generically, intake did not
finish its job.

### Mission rules for anything the generic rules miss

Most constraints reduce to "keep these two things apart", which the clearance
fields already cover. Some do not follow from any part's properties — they
follow from what the product *is*. Those go in `mission_rules`:

```jsonc
{
  "id": "lead_vector",
  "type": "min_separation",
  "between": ["ELEC_A", "ELEC_B"],
  "distance_mm": 35,
  "metric": "center",
  "severity": "blocker",
  "title": "ECG lead vector is long enough to resolve",
  "rationale": "A single-lead ECG measures the potential difference between "
               "two electrodes. Signal amplitude scales with how much of the "
               "heart's dipole the pair spans, so electrodes placed close "
               "together produce a low-amplitude trace that no amount of gain "
               "recovers cleanly. 35 mm is the practical floor for a chest patch."
}
```

Nothing about an electrode's datasheet implies this. It is a fact about
single-lead ECG, and it is exactly the kind of constraint a generic PCB tool
has no way to know.

### Say when a number is a guess

If a dimension came from a category norm rather than a datasheet, or a
clearance is an engineering judgment rather than a spec, say so in
`placement_notes` or the library's `notes` block. The report surfaces data
warnings; unmarked guesses are worse than marked ones.

---

## Questions worth asking

Intake is an interview, not a form. The answers that change the constraint set
most:

**Physical.** How big can it be? What is it mounted in or on? Does anything
have to be reachable after assembly? Is it sealed?

**Human contact.** Does it touch skin? For how long? Is the user a patient, an
operator, or a technician? Are they wearing gloves? Can they see it while using
it?

**Environment.** Indoors or out? Temperature range? Moisture, dust, vibration?
Is it ever charged, cleaned, or sterilised?

**Signal.** What is the smallest signal it measures, in volts? What is the
loudest thing on the board? Is there a radio, and what has to reach it?

**Power.** What is the source? What is the runtime target? What is the peak
current, and what dissipates it?

**Regulatory.** Medical, automotive, aviation, consumer? Which standard applies,
and does it set a hard number the design must clear?

The last one is where thresholds like the 43 °C skin limit come from. When a
standard sets the number, cite it in the rationale.

---

## Worked example

`parts/ecg-patch-parts.json` and `layouts/ecg-patch-naive.json` are the output
of this process for the paragraph at the top of this page. Seven parts, eight
placements, one mission rule, two mission thresholds, eleven rationale entries.

The naive layout is a deliberately constraint-blind arrangement: parts grouped
by schematic convenience rather than by mission. It fails ten checks across
every constraint family. `layouts/ecg-patch-missionpcb.json` is the same BOM in
the same enclosure, arranged against the constraints, and passes all 45.

```
$ ./run_demo.sh

ECG Patch - Naive Layout:        FAIL - 35 passed, 10 failed
ECG Patch - MissionPCB Layout:   PASS - 45 passed,  0 failed
ECG Patch - MissionPCB Solved:   PASS - 45 passed,  0 failed
```

The third row is the solver reaching an equivalent result on its own, starting
from the broken board.

---

## Adapting to a different product

Nothing in `src/constraint_engine/` is ECG-specific. Every product-specific
fact lives in the two JSON files. A different mission means writing new data,
not new code:

- A **drone flight controller** would set `skin_contact_clearance_mm: 0`
  (nothing touches a person), add vibration-sensitive parts, give the motor
  drivers large `heat_zone_radius_mm` and noise clearances, and add a mission
  rule keeping the IMU near the airframe's centre of mass.
- A **wearable hearing aid** would keep the skin-contact rules, shrink the
  enclosure by an order of magnitude, and add a mission rule enforcing
  microphone-to-speaker separation to prevent acoustic feedback.
- An **industrial sensor node** would drop skin contact entirely and add
  clearances driven by an operating temperature range instead.

If a new mission needs a genuinely new *kind* of check — not a new number, a
new relation — that is a code change in `rules.py`. Everything else is data.
