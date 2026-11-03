# Maintainer content sweep

This is a development experiment for BCUS98158 v03.00, not a player feature or a complete game catalogue. `scripts/content_sweep.py` drives the game with scripted pad input, saves window screenshots and provenance into ignored scratch storage, and exports metadata-only candidate templates. The shipped starter is not changed. Candidates require original-asset lookup, both-stage reconstruction and exact native preparation before acceptance.

## Running

Use a private game root, cache and output; keep game data and raw shader files out of Git. On the shared machine, check `tasklist /FI "IMAGENAME eq gt5p.exe"` before each run and use `C:\tmp\gt5p-testlock\run_locked.py --label <unit> -- <command>` for each game run and test. Do not run two at once. For example, using the Python and input locations in the machine-local instructions:

```powershell
python scripts/content_sweep.py setup --root scratch/content-sweep
python scripts/content_sweep.py check --plan config/content-sweep/gt5p-prologue.json
python scripts/content_sweep.py run --root scratch/content-sweep --out scratch/content-sweep/studio --plan config/content-sweep/gt5p-prologue.json --only course-daytona --cache scratch/content-sweep/shadercache --attempts 2
python scripts/content_sweep.py report --root scratch/content-sweep --out scratch/content-sweep/studio --plan config/content-sweep/gt5p-prologue.json --cache scratch/content-sweep/shadercache
```

The tool sets a private shader cache, disables settings and verbose logging, hides the specified filesystem path, records window images, and terminates the owned game in `finally`. Use a warmed private cache: the fixed input timing is sensitive to frame rate. `state.json` records attempts; done chunks are skipped, failed chunks retry up to `--attempts`, and `--force` reruns even a done chunk. A process interrupted before a result is not proof of completion. Inspect screenshots, not just the generic page-label and milestone checks. `contact` assembles them for review; `probe` supports menu-flow investigation. The report uses `pipeline_template_coverage.py` and keeps exports under the output directory.

## Plan and limits

The version-1 JSON plan defines resolution/MSAA, optional timing overrides, dealer grid coordinates and car counts, and Arcade slot numbers and number of race samples. A null car count triggers a survey; `plan-update` proposes counts from carousel text and still needs image review. Chunks have at most 64 pad presses. Each dealership chunk starts a new game and visits a maker page and successive studio pages; each course chunk records grid and time-separated race samples. The input sequence is open loop: a label or milestone does not identify a particular car or verify a camera change. The automated resume status is therefore provisional until screenshots are reviewed.

At 1080p/2x, the existing run captured 31 maker chunks. Image review found that Mazda car 0 and car 1 both showed the Atenza in the first attempt, despite passing checks. A 104.8-second retry showed the Atenza, RX-7 and RX-8 in order; its final car had no new first-seen links attributed to it. Concept by GT's last three planned car shots show loading screens; its attempt is marked failed. Those are not complete car coverage. High Speed Ring, Daytona and Fuji Speedway F screenshots show their starting grids and races; their measured run times were 167.2, 172.3 and 172.2 seconds respectively. The four race screenshots per course appear to use the same in-car view: no scripted camera change is implemented. Slot 3 also reached Eiger Nordwand, confirmed by its grid and race screenshots in 183.6 seconds; slot 4 reached Suzuka Circuit in 166.6 seconds, but the car stopped against a barrier and later samples repeat the same location. Slot 5 reached London in 166.9 seconds, but the car was stationary against a barrier in every race image. A further selection attempt at slot 6 also showed London (169.0 seconds), suggesting a clamped end of list; higher slots remain unverified. The comparison below includes the six distinct measured course selections, excluding the duplicate slot 6 probe. A screenshot can also catch a loading or transition state even when the underlying content later appears.

The sweep collects observed states under one save, settings, renderer and scripted route. Attribution assigns first-seen links by time, so delayed compilation/loading and boot work can shift ownership between units. It does not prove a key is exclusive to a car, that all visual states were exercised, or that game-wide coverage has saturated. GT5 has a much larger and different catalogue: neither these timings nor counts can be extrapolated as a completed GT5 sweep. Its plan, navigation, save prerequisites, timing and per-car identity checks must be re-derived, and the output revalidated for that game version.

## Partial comparison (2026-11-04)

The latest attempts across 37 planned chunks took 3,779.1 seconds in aggregate, excluding retries and lock waits. The scratch report contains per-chunk elapsed seconds and per-unit first-seen counts. It includes the failed Concept attempt, so it is a partial observation, not proof of every planned car. Against the 5,669-record starter, the quarantined union has 13,459 records: 7,790 additional candidates, including 1,747 using both existing starter programs and 6,043 needing at least one program not in the starter. Forty-seven conflicting keys were quarantined within grouped sessions; no further conflicts were reported between groups and baseline. These are metadata comparisons, not successful preparation.

In plan order, the 71 automatically passing car-studio units account for 2,189 first-seen candidates; the first 10 account for 198 and the last 10 for 397, with a median of 5 per unit. This does not demonstrate saturation: maker-page arrivals account for much of the discovery, and asynchronous loading can attribute a car's links to another interval. The time-ordered per-unit rows use first-seen exported keys before conflict quarantine; their final cumulative count is 7,794, four more than the quarantined delta. Rows, including failures, are in `scratch/content-sweep/studio/report.md`; chunk exports and the delta stay in scratch. There is no reliable extrapolation from these counts to 1,000 GT5 cars.

An exact filename check against the specified local `library-v1/all` catalogue found no matching `.fp` filename for 7,790 of 7,790 candidate records (2,196 distinct fragment identifiers). However, a control found matching filenames for only 3 of the 5,669 already verified starter records. The directory contained 8,142 `.fp` files, and a sampled filename matched its payload SHA-256. This striking control failure makes the candidate count a statement about this directory snapshot only, not evidence that those programs have no asset payload. Reconcile the catalogue's scope and identifiers with the original-volume map before using this statistic to plan GT5 coverage.

## Catalogue reconciliation (2026-11-04, integration branch)

The filename check above compares template `fp.sha256` with catalogue file
names. Those are different identities: catalogue files are named by the raw
payload SHA-256, which includes inline constants, while templates use the
instruction identity from `shader_coverage.fp_identity` (constants zeroed).
That explains the 3-of-5,669 control result.

Matching by instruction identity instead, using
`shader_enumerate.fragment_inventory` over the same `library-v1/all` snapshot:

| set | records | distinct FP | FP in catalogue | FP absent | records with an absent FP |
| --- | ---: | ---: | ---: | ---: | ---: |
| starter (control) | 5,669 | 1,404 | 1,189 | 215 | 986 |
| sweep candidates (37 chunks) | 7,790 | 2,196 | 1,974 | 222 | 935 |

The control now agrees with `docs/coverage-enumeration.md` (1,189 / 215).
Of the 1,605 candidate fragment programs not already in the starter, 1,420
are in the catalogue, so shader-first enumeration already compiles their
bytecode. 185 are absent from the catalogue: only observation (this sweep or
player collection) can supply those. Candidates remain unverified metadata
until the usual preparation acceptance.
