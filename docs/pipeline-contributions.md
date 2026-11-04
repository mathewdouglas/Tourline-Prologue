# Contributing pipeline templates

## Automatic verification after play (Phase 202)

`Collect pipeline template.cmd` records during ordinary launcher-owned play as
before. After the game closes and the collection settings check passes, it saves
the complete captured metadata privately, then finds original programs and
independently reconstructs both shaders and exact native pipelines. Verification
never runs alongside the owned game. It uses the launcher's exclusive storage
lease and separate private `cv/<identity>` checkpoints; it never selects or edits
the player's prepared cache. Native children have private kill-on-close jobs,
offline-entry guards, bounded logs and timeouts; vertex worker budgets stay intact.

After play, a **Tourline Prologue - Collection verification** window styled like
the shader precompiler shows
the current lookup/shader/native stage, available stage counts and elapsed time.
Counts describe that stage, not a whole-operation percentage or estimated time.
Long compiler/native batches can show a working message until the batch finishes.
The result stays visible with verified/pending totals and the share filename;
close it to finish the command. No additional UI libraries are required.

**Cancel** or closing the working window requests cooperative cancellation. The
window waits for owned child/lease cleanup, then confirms that completed work is
kept. Close that result window and use `Resume pipeline verification.cmd` to
continue in a new progress window. Errors also leave a visible result and retain
the private input/checkpoints. `GT5P_COLLECT_VERIFY_UI=0` restores console-only
verification without disabling verification or changing its acceptance checks.

Keep the collection process open. Ctrl+C also cancels verification;
`Resume pipeline verification.cmd` continues
the most recent captured session without launching a game. Completed lookup is
reused, cached shader bytes are checked, and native pipelines are revalidated.
Cancellation during an unfinished lookup restarts that bounded search on resume.
An optional session-local `verify.cancel` marker also requests cancellation; only
that marker is cleared on the next owned resume. Game/cache/recorder bytes stay
local. `GT5P_COLLECT_VERIFY=0` leaves collection pending without publishing a share
file; explicit Resume still requests verification.

Only successful independently prepared records reach `share-this-template.json`.
Unresolved or rejected records stay in private `pending-template.json`, and the
local `verification.json` reports both counts. After a later search-map/decoder
update, newly verified rows can produce an additive, digest-named share file;
the earlier verified export remains unchanged. Share the path printed by the
latest successful run. No report, recorder, original shader, DXBC or driver blob
is included in that metadata envelope. Failed/cancelled work retains the captured
input and previous exports. Nothing is uploaded or accepted into a release.
An incomplete native-process batch stops verification safely; partial native
logs never authorize publication. Resume revalidates completed cache work.

The packaged numeric search map covers 592 original SHDS-bearing/reference
containers, independently of the starter's 165 archive members. Whole volume,
ELF, decoded-member and program hashes gate reconstruction. This is a wider
bounded search, not archive-wide semantic discovery: unknown programs remain
pending. Existing limits remain 600 seconds/search, 128 MiB/oracle pool and
decoded member, 8,192 recorder files, 4,096 records/session. No new renderer
instrumentation, per-draw work, async policy or driver-cache clearing is added.

Player verification is useful local evidence, not authentication. Maintainers
must still locate/reconstruct candidates against their own original assets and
repeat native acceptance before updating a starter or release. The explicit
developer `export`/`--export-contribution` paths remain untrusted metadata export
tools; they do not claim post-play verification.

The development merged catalogue permits 65,536 records / 128 MiB, independently
of the existing 4,096-record collection-session and 32 MiB submission budgets.
Collect additional sessions as needed; review and original-asset/native proof
remain mandatory. The catalogue ceiling is not a count of verified shaders,
full-game coverage, or a promise to prepare that many within current worker,
memory and checkpoint budgets. Prologue and GT5 require separate compatibility
contracts.

Tourline ships a format-3 input template with vertex/fragment SHA-256
identifiers and numeric translation/native pipeline state. A list of hashes
alone cannot reproduce a pipeline: the same programs can be used with different
samplers, targets, blend/depth state, vertex layouts and renderer settings.
Contributions carry the existing complete records in a checked JSON envelope.
They expand observed coverage after verification; they do not require another
player to repeat every car/track combination.

## Player workflow (development feature)

In a matching new launcher/engine/helper package, **F1 -> Debug** also provides:

- **Collect pipelines:** closes the current game and restarts through the normal
  launcher into opt-in collection. Close that game to verify it afterward.
- **Verify last collection:** closes the game and verifies/resumes the latest
  saved collection, without launching another game. A missing selection is
  reported on the settings page before the game is closed.
- **Prepare shaders:** closes the game and opens the existing shader precompiler
  for saved settings, with its ordinary progress/cancel/resume behavior. Launch
  the game normally afterward.

Use Enter/Cross or click **Start**; Left/Right never activates these actions.
Help text explains that the current game will close. Collection still requires
the supported default settings below. During an active collection, close the
game to finish it before starting another tool. Direct engine launches and older
or incomplete packages cannot start these actions; the CMD entries remain usable.
`GT5P_PIPELINE_TOOLS=0` disables the new launcher handoffs. They retain normal
game-job ownership, storage locks, metadata-only export and verification rules.

The next package can include **Collect pipeline template.cmd**. The published
v0.2.2 package predates this command. Complete ordinary setup and launch the
game once first. Close the game before collection.

1. Use 720p or 1080p, 16:9, anisotropy 16 and smooth colour enabled. Keep these
   settings throughout the collection. Higher resolutions, ultrawide translation
   and custom renderer overrides are currently rejected before collection.
2. Run **Collect pipeline template.cmd**. It reads the launcher's selected
   storage location, creates a separate private recording and launches the
   ordinary launcher. Visit useful tracks/cars/cameras/menus, then close normally.
   Collection is opt-in and adds diagnostic I/O; do not benchmark with it enabled.
3. The command prints the path to **share-this-template.json**, under your storage
   folder's `pipeline-contributions/session-.../`. Send **only that JSON** using
   the repository's pipeline-template contribution issue or your chosen channel.
   You can describe the content visited separately, without local paths.

The existing launcher still owns the game job, storage locks and settings
restarts. Collection does not change async shader/pipeline policy, upload
anything, install submissions, change the prepared-cache pointer or delete caches.
The existing recorder switch is enabled only for the child session, limited to
4,096 links. At least 1 GiB of free space is required. That is a preflight reserve,
not a guarantee against filling a disk during an extended session. The recorder
currently requires an ASCII path shorter than 448 characters. Truncated/unsupported
joins can be excluded; this file is not a whole-session coverage percentage.

The adjacent **private-recorder** directory contains original program data and
translation diagnostics. It stays local, as do shadercache, game files and logs.
Do not ZIP or share the session directory. Failed/cancelled collection leaves
those local files for inspection; it does not produce a verified coverage claim.
Ordinary play remains unchanged when the collection command is not used.

An existing private recording can also be exported without launching a game:

```powershell
preparation/GT5P-Prepare.exe --export-contribution --install . `
  --storage <selected-storage> --trace <private-recorder> `
  --output <new-share-file.json>
```

Use `--cache <actual-cache-used>` when that session used a different cache,
such as `--no-prepared`. The cache must be inside the selected storage. Existing
outputs are preserved. This export currently requires the same default settings.

## File contract

`tourline-pipeline-contribution`, version 1, contains only `schema`, `version`,
`template_sha256` and `template`. New exports use template format 3. The checksum
covers the canonical validated template as sent. Format-2 envelopes from older
players remain accepted: their original checksum/schema are checked before
conversion to format 3. Renderer output differences do not create new inputs.

Format 3 pins the original ELF, Windows x64 recipe/key/root-signature ABI,
default renderer settings and translation policy. It has no renderer source hash.
Each record contains only `vp` and `fp` SHA-256 identities/sizes, `vp_gpu`, the
complete numeric `state`, and `native.words` / ATTR input elements. The historical
field `key` now holds a **64-character SHA-256 input identity**, with domain
`gt5p-pipeline-input-v3\n`, over sorted, compact JSON of those five input fields.
It is not a native pipeline key. Native descriptor shader-length words 4/5 and
8/9 are zero: compilation supplies their actual values locally. Unknown fields,
nonzero output lengths and an identity/content mismatch fail strict validation.

No `vs`, `ps`, `vp_source`, `fp_source`, native pipeline hash, renderer-source
pin, filenames, usernames, timestamps, annotations, source text, microcode, DXBC
or driver blobs belong in a format-3 template. Vertex identity hashes the bounded
original program; fragment identity hashes the structural program with inline
constants normalized. A checksum detects changes; it does not authenticate a
contributor or establish observation, reconstruction, residency or hitch freedom.

Inputs have bounded size, nesting and record counts. Duplicate JSON fields,
unknown fields, nonfinite numbers, incompatible versions/contracts, conflicting
records and checksum changes cannot silently become shipped entries. Local
recorder identifiers are checked before opening their program/recipe files.
Branching vertex contexts and unsupported compiler flags remain excluded.

## Maintainer workflow

Keep submissions separate from the shipped bundle. Exporting a developer template
does not require a special binary format:

```powershell
python scripts/pipeline_contribution.py export --template <session-template.json> `
  --output <new-contribution.json>
python scripts/pipeline_contribution.py review `
  --baseline assets/pipeline-templates/gt5p-disc-v2 `
  --submission <contribution-a.json> --submission <contribution-b.json> `
  --output scratch/contribution-review
```

Review accepts at most 16 submissions and 32 MiB total. It deduplicates known
records, reports additional program/input identities and quarantines a claimed input
identity with different content. Different numeric inputs have different identities. It preserves the baseline and never chooses a conflicting
record by upload order or majority. `candidates.json` is an ordinary format-3
template containing only unambiguous additional records. `review.json` is an
overlap/conflict report, not shader or native-pipeline verification.

Locate candidate program hashes in your own original assets, adding verified
asset locations where necessary. Hashes alone do not supply missing asset offsets.
The maintainer can search the original packed game directly, using a private
recorder only for search anchors:

```powershell
python scripts/pipeline_volume_search.py --template <candidates.json> `
  --trace <private-recorder> --volume <original-GT.VOL> --elf <original-EMAIN.ELF> `
  --volume-map assets/pipeline-templates/gt5p-disc-v2/volume-map.json `
  --known-map assets/pipeline-templates/gt5p-disc-v2/player-map.json `
  --output scratch/new-program-locations
```

Use the production `volume_reader.dll` through `GT5P_PREPARE_VOLUME_LIBRARY` in
source runs. This searches only already verified archive members plus the ELF;
it is not an archive-wide catalogue. Whole archive, ELF, member and program
identities must verify. Members over 128 MiB are skipped; missing programs stay
unresolved. Search is bounded to ten minutes and keeps decoded members in memory,
without extracting another asset copy. Merge positively verified location rows
into the player/supplemental maps, retaining exact container coverage in the
volume map. New containers require separate verified numeric archive locations.

Use the existing `pipeline_template.py prepare` with `candidates.json`, your own
game/production decoder/engine and a fresh private output. Require successful translation/compilation of both shaders, native pipeline creation,
persistence and a fresh-process lookup through the runtime cache. The engine
computes its keys; there are no shipped output expectations. Unsupported or unresolved
records stay out. A metadata submission alone never authorizes different renderer
settings, root signatures or capture-derived pass assumptions.

```powershell
# Run the normal fresh native prepare first; then use its local report:
python scripts/pipeline_contribution.py accept `
  --baseline assets/pipeline-templates/gt5p-disc-v2 `
  --candidates scratch/contribution-review/candidates.json `
  --proof <your-local-preparation/report.json> --output <new-merged-template.json>
```

Acceptance requires successful default-stage preparation for every exact candidate
input identity, matching native results, persisted-driver inventory, complete runtime
lookup counts and candidate-file digest. Output hashes are local report fields.
Use **your own locally generated report**, never a report supplied by a contributor.
These files are not cryptographically authenticated against someone editing
both a template and a purported proof. The command only writes a new merged
template; it does not modify the shipped starter or publish a release.

Phase 198 reviewed the second Phase 197 packaged HSR replay export: all 1,951
records already occur in the expanded 3,102-record starter, with zero additional
records or conflicts. No records are promoted from this replay. This is overlap
evidence for that export, not whole-game coverage or an independent native proof.

Before shipping, reissue the metadata bundle and complete player/volume lookup
maps, regenerate the warmup plan for its new bundle digest, validate the full
generation and player package, and test representative rendering. New numeric
contexts also need live acceptance. No contributed shader/program/cache bytes
belong in git or a release. Templates remain an observed subset; asset-derived
rules and additional settings/context work remain separate roadmap items.

## Format migration and regression references

`scripts/pipeline_template_inputs.py --template <format-2 bundle> --output <new bundle>`
converts identifier/numeric metadata only. Add `--warmup-plan <old plan>
--output-plan <new plan>` to preserve observed membership as input identities.
The converter preserves the four program/location maps byte for byte. Re-pin
an enumeration plan's `template_sha256` to the new bundle index with
`scripts/release/build_enumeration.py` (see coverage-enumeration); for the shipped
migration it reproduced the existing plan apart from a trailing newline, so program,
profile and job membership did not change. The shipped path retains `gt5p-disc-v2` for package
compatibility; its index and shards declare format 3.

For maintainer regression checks, `pipeline_template.py prepare` accepts
`--reference-template <private format-2 reference>` or `--reference-report
<private successful format-3 report.json>`. This strict mode compares every
local source, bytecode and native identifier with that reference before successful
publication. These references stay outside the starter and submissions. Ordinary
acceptance proves current-engine construction/persistence/lookup instead of requiring
an earlier renderer's outputs. A changed renderer may legitimately change outputs.

See [input format design and validation](template-input-format.md). Older helpers
cannot read format 3; package the matching helper. Format-2 contributions remain
readable without a renderer-contract reissue, but always need fresh maintainer proof.
