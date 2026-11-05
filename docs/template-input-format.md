# Input-only pipeline templates

Format 3 separates portable reconstruction inputs from a renderer's outputs.
A source comment, offline transport change or shader optimization no longer
requires editing the starter. This does not expand pipeline coverage or alter
normal renderer behavior. Key/root-signature ABI, default settings, translation
policy and the original game ELF remain compatibility requirements.

## Record and bundle contract

The template schema remains `gt5p-pipeline-template`; `version` is 3. Its
compatibility object has `abi`, `key_version`, `root_signature_keyed`,
`renderer_settings`, `elf_sha256` and `translation_policy`. It has no
`renderer_sha256`. Sharded bundles declare version 3 and retain bounded part
names, checksums, record/part/byte ceilings and strict JSON/field validation.

Each record has `vp`, `fp`, `vp_gpu`, `state`, `native` and `key`. Program
identities and sizes, every numeric translation field, the numeric descriptor
and all ATTR input elements are inputs. Descriptor words 4/5 and 8/9, which
formerly stored compiled VS/PS byte lengths, must be zero. Actual bytecode
lengths are filled locally after compilation. Pointer/unused-stage/semantic
checks remain unchanged. All `vs`, `ps`, `vp_source` and `fp_source` fields
are absent. No native pipeline key is stored.

The historical `key` name denotes the 64-character lowercase SHA-256 of:

```
b"gt5p-pipeline-input-v3\n" + canonical_json({vp, fp, vp_gpu, state, native})
```

Canonical JSON uses sorted object keys, compact separators, ASCII encoding
and finite numbers. Integer bounds/types and fixed sampler spelling are checked
before use. Record order does not enter an identity. Identical inputs deduplicate;
changing an input requires a different identity. Strict readers reject a claimed
identity/content mismatch. Maintainer review preserves structurally valid claimed
mismatches only long enough to quarantine the identity and all submitted versions.
Unknown fields, pointers, invalid types and incompatible contracts still reject.

## Preparation and regression verification

The current installed engine/decoder produces shader source/code identifiers and
bytecode. The existing bounded derive-worker protocol checks its returned source
and code identities. The host fills bytecode lengths and derives a proposed native
key using the pinned ABI/root signature. The unchanged engine independently
computes its own actual key and must confirm it while creating/persisting the
pipeline. This host proposal is an offline-transport requirement, not a shipped
expectation. No runtime/renderer patch is changed.

After creation, fresh sequential native processes repeat every unique request.
Every ordinary driver-cache lookup must find a persisted blob: request, creation,
driver-call and cached-blob counts must all equal the unique pipeline count.
Every result key and final recipe/shader/driver inventory is checked. A missing
marker, partial result, lookup miss or invalid inventory withholds success.
Distinct inputs may legitimately produce one native key; requests are deduplicated
by the locally produced key while reports preserve every input identity.

Local `report.json` includes `input_key` joins, `derived_records`, native results
and runtime lookup counts. The nested `di/` checkpoint pins actual engine/decoder
hashes and root signature and records content-addressed shader manifests. It saves
completed work before polling cancellation. Resume rechecks shader bytes and
recreates/revalidates native pipelines. Reports and generated caches remain private.

Maintainers can opt into a strict comparison using:

```
python scripts/pipeline_template.py prepare ... --reference-report <local-report.json>
python scripts/pipeline_template.py prepare ... --reference-template <old-format-2>
```

Strict mode compares every source, bytecode and native identifier against that
reference before successful publication. A format-3 reference report must itself
have complete native/persistence/lookup proof and input-consistent local output
metadata. The reference is not bundled or exported as an expectation. A renderer
change is allowed to change outputs under ordinary current-engine verification;
maintainers decide whether a regression reference should change.

## Consumers and retained caches

Warmup plan version 2 stores menu/race input identities in context
`default-template-inputs-v3`. Its native lists are derived only from successful
local results. Native membership files and shader packs keep their existing runtime
formats. Pack dependencies come from local output metadata joined to those input
identities, including for standalone pack generation. Warmup metadata is bounded
to 1 MiB to accommodate SHA-256 identities; the 4,096-target ceiling is unchanged.
Observed membership is preserved, and no new pass/phase ownership is inferred.

Contribution envelope version 1 accepts either template format. Original format-2
checksums are verified before conversion, and output/source-contract differences
are discarded. Dedupe, overlap, candidate selection and collection publication use
input identities. Every candidate still needs original-asset/current-native proof.
Player reports and metadata submissions are not authenticated maintainer proof.

Generation identity still includes installed engine/decoder hashes, input metadata,
plan/pack/enumeration pins and, for format 3, the saved settings selection. Engine
or settings changes select another generation without changing the starter.
Old selected generations, learned files and pointers remain intact on cancellation
or failure. No cache is deleted automatically.

A format-2 generation can provide bounded, checked driver hints after current
outputs have been derived. Its shaders are recompiled: that generation lacks an
input-keyed shader derivation manifest. An engine/decoder-matched format-3 generation
can supply verified input-keyed shader derivations, with existing 128 MiB / 60 s
bounds and read-only source/link checks. Engine changes rederive shaders. Driver
hints always go through native construction and the subsequent runtime lookup.
Recipes, learned membership and packs are not imported.

Maintainer enumeration planning also consumes inputs. Exact output-key recall
requires `shader_enumerate.py recall --reference-report <local-report.json>`;
without a reference it reports input/profile coverage and withholds output-key
claims. Content-sweep unit reports bridge native logs through unambiguous verified
local provenance joins; missing/ambiguous joins are counted separately.

Maps remain program-identity keyed and unchanged. The enumeration plan's template
pin is reissued once for migration; its programs, profiles and jobs are unchanged.
Future renderer source changes do not change this input-template pin.

## Migration and rollback

```
python scripts/pipeline_template_inputs.py --template <format-2 bundle> \
  --output <new bundle> --warmup-plan <old plan> --output-plan <new plan>
```

The converter drops output identifiers/lengths and the renderer source pin,
computes input identities and preserves the four numeric location maps. The
shipped directory retains `gt5p-disc-v2` for package-path compatibility. New exports
are format 3. Readers convert format 2 on load, including old contribution envelopes;
legacy native-key membership can be converted with its original format-2 bundle.
Older frozen helpers cannot read format 3; distribute the matching helper.

`GT5P_PREPARE_INPUT_TEMPLATE=0` disables the new preparation path and requires a
separate format-2 template with its strict renderer/output gates. It rejects a
format-3 starter. Format 3 uses renderer fragment batches, default chunk size 256;
`GT5P_PREPARE_FRAGMENT_CHUNK=4096` restores the previous maximum chunk size.
`--fragment-mode legacy` is available with the format-2 rollback. Existing worker,
handoff, native hash, I/O, pack and runtime switches retain their meanings.

## Validation

The locked evidence and measured results are recorded in the new phase in
[progress](progress.md). Authored checks are `scripts/test/pipeline_template_inputs.py`
and `scripts/test/pipeline_inputs_frozen_native.py`. The latter disables unrelated
shader enumeration to isolate the complete starter/native proof, compares against
a private format-2 reference, and checks old-cache/selection preservation. Live
routes, additional GPUs, whole-game/settings coverage and stutter improvements are
outside this format migration.

Modes of `pipeline_inputs_frozen_native.py` (each its own locked run, private
output): `fresh` (default; cancels at native input and resumes, `--limit N` runs a
subset), `legacy-seed` (builds a format-2 generation with
`GT5P_PREPARE_INPUT_TEMPLATE=0`) and `incremental` (`--previous-cache` from a
legacy seed or a smaller format-3 run). `--source-comment-probe` appends a harmless
comment to the helper's source resource and expects the same template digest with a
different engine hash. Accepted evidence: full 12,669 fresh with cancel/resume (all
outputs equal the format-2 reference; native and fresh-process lookup 12,669 each);
frozen 32-record smoke after the rebase onto the enumeration speed work; format-2 ->
format-3 incremental reuse (32 blobs copied, shaders recompiled); format-3 growth
(32 -> 33 records, 32 blobs reused, one created); the comment probe; the strict
`--reference-template` regression; and the native pack reader on the full generation.
In a subset the 100 ms status debounce can hide non-zero native-input counts, so
subset runs cancel on any `Native input` status; the full run requires published
inputs. A 32-record format-3 run with a progress callback caught a reuse progress
payload that lacked `total`; it is fixed and the formatter no longer requires it.
