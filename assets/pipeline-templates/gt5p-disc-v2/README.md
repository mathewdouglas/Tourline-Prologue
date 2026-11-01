This optional developer starter contains 2,892 verified pipeline records for
BCUS98158 version 3. It contains program identifiers and numeric translation/native
state only. It contains no shader microcode, source, DXBC or driver binaries.

The records came from local menu/High Speed Ring/Daytona play and an additional
Fuji Speedway F (Course Select slot 2) session covering the grid/opening section. Both
shader stages were reconstructed from original assets, their identifiers checked,
and native keys reproduced and pipelines created on the test machine. Unsupported
or unavailable programs and branching vertex contexts are excluded. This is an
observed-state template, not independent recovery of material/pass ownership or
whole-game coverage. It does not cover every car or every part of these tracks.

The previous 2,334 records are unchanged. Phase 180 adds 558 verified records;
nine conflicting session keys were quarantined, and three branching contexts and
eleven missing joins were excluded at export. The original 2,334-record batch
and the new 558-record batch each passed an empty-application-cache shader/native
proof. This is not a single fresh-cache 2,892-record compilation experiment.
OS/driver caches remained warm. No consistent stutter improvement is claimed.

`index.json` verifies the metadata shards. Format 2 pins the renderer source
contract, Windows x64 recipe/key ABI, explicit default settings and original ELF.
The preparer verifies locally rebuilt shaders and actual root-signature/native
keys before accepting anything. Incompatibilities remain on the demand path.
Driver results are constructed locally for the user's GPU and stay local.

Developer preparation uses exact fragment batching by default;
`--fragment-mode legacy` is the rollback.
Matching checkpointed template output supports `--resume`, verifying cached
shader identifiers and revalidating native pipelines before acceptance. A changed
template can read verified hints from an older cache using `--reuse-cache`.

`asset-map.json` is a separately versioned hash/offset map with 286 supplemental
locations: the earlier 119 programs outside supported SHDS tables plus all 167
new program identities. The new locations can overlap supported SHDS lookup.
Supply `--assets <original unpacked GT.VOL directory>`
to select it automatically. It contains container/program hashes, file offsets,
sizes and byte order only. Container hashes and program identities are verified
locally before compilation; captured programs are not needed by users.

See [the preparation workflow](../../../docs/shader-precompile.md). Pass this
directory to `scripts/pipeline_template.py prepare --template`. Nothing loads it
by default. The optional v0.2 player helper uses `player-map.json`, a complete
hash/offset map for all 1,143 unique programs (348 vertex, 795 fragment), using
the user's original game files and verified ELF, without a developer
catalogue. The smaller `asset-map.json` remains the supplemental developer map.
Templates do not establish menu/race preload ownership; preparation
does not fabricate those membership indices. No launcher/release default or
zero-stutter claim is made.

Development direct preparation uses `volume-map.json`, numeric locations for 104 required
archive members plus parameter locations in the user's verified ELF. It contains
no keys or file names. The optional helper can read the original GT.VOL directly,
verify each decoded container and all 1,143 programs, and avoid an unpacked asset
copy. Both ELF and volume SHA-256 must match this supported disc build. The
legacy unpacked-assets flow remains available. Other builds/modded volumes need
separately verified maps. The published v0.2 package remains unchanged.
