This optional development starter contains **12,669 verified pipeline records**
for BCUS98158 version 3, with **3,446 original program identities (622 VP /
2,824 FP)**. It contains identifiers and numeric state only, without program,
HLSL, DXBC or driver-cache bytes.

Phase 212 accepts 7,000 content-sweep additions and preserves all previous 5,669
records. Another 790 records depending on 185 unresolved FP identities stay out;
47 earlier conflicting keys remain quarantined. Every accepted record passes
original-asset reconstruction of both shaders, exact native keys and persistence.
All programs are verified directly from the original GT.VOL/ELF. The complete
player map has 3,446 locations; the volume map has 297 required archive members,
adding 96 members already present in the unchanged 592-container search map.
The supplemental asset map is extended with the newly located programs.

The candidate source-contract pin is explicitly reissued from Phase 210 to
Phase 211 after source comparison, preserving all record fields and rendering
keys. Full fresh frozen-helper preparation passes all 12,669 native pipelines in
4,096/4,096/4,096/381 chunks with cancellation/resume and persisted blobs. The
observed warmup membership is unchanged and pinned to the new bundle index;
new keys remain on demand. A representative HSR replay is checked; this does not
establish every car/camera/state, whole-game, arbitrary-settings, GT5 or stutter
coverage. Published v0.2.3 is unchanged. See [Phase 212](../../../docs/progress.md).

`index.json` verifies the 99 metadata shards. Format 2 pins the renderer source
contract, Windows x64 recipe/key ABI, default settings and original ELF. The
preparer checks rebuilt shader/source identifiers, native keys and persisted
driver blobs locally; unavailable or incompatible entries stay on demand.

`player-map.json` covers exactly all 3,446 bundled original programs.
`volume-map.json` covers their 297 archive members plus parameter locations in
the verified ELF, without keys or filenames. Both ELF and whole-volume hashes,
every decoded member and every selected slice must verify. Other builds or
modified volumes require separately verified maps.

`asset-map.json` contains 1,870 supplemental developer locations: the previous
305 plus 1,565 new identities. It can overlap supported SHDS lookup. The legacy
unpacked-assets path uses verified container hashes, offsets, sizes and byte order;
the optional player helper can read the packed game without a developer catalogue
or another unpacked asset copy. The separate 592-container `search-map.json`
supports post-play verification and adds no pipeline coverage by itself.

The warmup plan retains 1,466 menu / 2,113 race keys (3,546 distinct), including
previously observed prepass requests. Its new template digest does not infer
material/pass ownership or phase membership for the additions.

See [the preparation workflow](../../../docs/shader-precompile.md) and
[contribution acceptance](../../../docs/pipeline-contributions.md). Preparation
remains optional. `--resume` verifies matching retained work and revalidates native
pipelines; `--reuse-cache` reads verified hints into a separately owned output.
`--fragment-mode legacy` restores the older fragment path. Driver blobs and
shader bytecode remain local to the user's GPU/cache and never ship here.

Historical expansions and their narrower controls remain in the progress log:
Phase 201 reached 4,450 records, Phase 206 reached 5,669, and Phase 212 preserves
every one of those earlier records. This update changes development metadata;
published v0.2.3, runtime defaults and async draw policy are unchanged.
