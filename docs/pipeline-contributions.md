# Contributing pipeline templates

The development merged catalogue permits 65,536 records / 128 MiB, independently
of the existing 4,096-record collection-session and 32 MiB submission budgets.
Collect additional sessions as needed; review and original-asset/native proof
remain mandatory. The catalogue ceiling is not a count of verified shaders,
full-game coverage, or a promise to prepare that many within current worker,
memory and checkpoint budgets. Prologue and GT5 require separate compatibility
contracts.

Tourline already ships a version-2 template with vertex/fragment SHA-256
identifiers and numeric translation/native pipeline state. A list of hashes
alone cannot reproduce a pipeline: the same programs can be used with different
samplers, targets, blend/depth state, vertex layouts and renderer settings.
Contributions carry the existing complete records in a checked JSON envelope.
They expand observed coverage after verification; they do not require another
player to repeat every car/track combination.

## Player workflow (development feature)

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
`template_sha256` and the existing format-2 `template`. The SHA-256 covers the
canonical validated template. The template pins game ELF identity, renderer
contract/settings, key/root-signature ABI and default translation policy. Records
contain both program identities, sizes, shader/source identifiers and complete
numeric translation/native state. No filenames, usernames, timestamps, arbitrary
annotations, source text, microcode, DXBC or driver blobs are allowed as fields.

Vertex identity is SHA-256 of the bounded original program; fragment identity
is SHA-256 of its structural program with inline constants normalized. The
16-character pipeline/source/bytecode identifiers are renderer hashes, not
SHA-256. A checksum catches changes; it does not authenticate a contributor or
prove that a pipeline was observed, reconstructed, resident or hitch-free.

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
records, reports additional program/pipeline identities and quarantines conflicting
versions of a key. It preserves the baseline and never chooses a conflicting
record by upload order or majority. `candidates.json` is an ordinary format-2
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
game/production decoder/engine and a fresh private output. Verify both shaders,
exact native keys and persisted driver blobs as usual. Unsupported or unresolved
records stay out. A metadata submission alone never authorizes different renderer
settings, root signatures or capture-derived pass assumptions.

```powershell
# Run the normal fresh native prepare first; then use its local report:
python scripts/pipeline_contribution.py accept `
  --baseline assets/pipeline-templates/gt5p-disc-v2 `
  --candidates scratch/contribution-review/candidates.json `
  --proof <your-local-preparation/report.json> --output <new-merged-template.json>
```

Acceptance requires successful default-stage preparation for every exact
candidate key, matching native results, driver inventory and candidate-file digest.
Use **your own locally generated report**, never a report supplied by a contributor.
These files are not cryptographically authenticated against someone editing
both a template and a purported proof. The command only writes a new merged
template; it does not modify the shipped starter or publish a release.

Before shipping, reissue the metadata bundle and complete player/volume lookup
maps, regenerate the warmup plan for its new bundle digest, validate the full
generation and player package, and test representative rendering. New numeric
contexts also need live acceptance. No contributed shader/program/cache bytes
belong in git or a release. Templates remain an observed subset; asset-derived
rules and additional settings/context work remain separate roadmap items.
