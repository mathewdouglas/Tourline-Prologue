"""Owner-only, bounded verified bytecode reuse for guarded offline batches."""
import os
import struct
from pathlib import Path

from shader_coverage import bounded_read, fnv64
from prepare_material_shaders import save_code

MARKER = b'GT5P_OFFLINE_HANDOFF_V2'
CODE_MARKER = b'GT5P_OFFLINE_CODE_V1'
MAX_BYTES = 128 * 1024 * 1024
MAX_RECIPE_BYTES = 16 * 1024 * 1024


def supported_engine(engine, marker=MARKER):
    # The statically linked game engine is ~180 MiB. Scan with bounded buffers,
    # rather than allocating another executable-sized Python byte string.
    with engine.open('rb') as stream:
        if os.fstat(stream.fileno()).st_size > 256*1024*1024:
            return False  # Auto keeps the legacy path for larger/unknown engines.
        previous=b'';total=0
        while chunk:=stream.read(1024*1024):
            total+=len(chunk)
            if total>256*1024*1024:return False
            if marker in previous+chunk:return True
            previous=chunk[-len(marker)+1:]
    return False


def choice(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_HANDOFF','auto')
    if value not in ('auto','0','1'):
        raise ValueError('GT5P_PREPARE_HANDOFF must be unset, auto, 0, or 1')
    return value


def code_choice(environ=None):
    value=(os.environ if environ is None else environ).get('GT5P_PREPARE_CODE_BUNDLE','auto')
    if value not in ('auto','0','1'):
        raise ValueError('GT5P_PREPARE_CODE_BUNDLE must be unset, auto, 0, or 1')
    return value


class NativeRequests:
    def __init__(self, engine, cache):
        selected = choice()
        supported = False if selected == '0' else supported_engine(engine)
        if selected == '1' and not supported:
            raise ValueError('Native handoff requires a matching engine')
        self.enabled = selected != '0' and supported
        code_mode=code_choice()
        self.code_enabled=self.enabled and code_mode!='0' and supported_engine(engine,CODE_MARKER)
        if code_mode=='1' and not self.code_enabled:
            raise ValueError('Bytecode bundle requires a matching engine and native handoff')
        self.bundle=None
        self.directory = Path(cache)/'warmup-v1'
        self.pool = {}
        self.bytes = 0
        self.results = {}
        self.recipes = {}
        self.recipe_bytes = 0
        if self.enabled:self.directory.mkdir(exist_ok=True)
        self.report = dict(enabled=self.enabled,byte_budget=MAX_BYTES,
            bytecode_requests=0,verified_memory_hits=0,file_checks_or_writes=0,retained_bytes=0)

    def write(self, proof, recipe, vs, ps):
        if len(recipe)!=2760:raise ValueError('Native recipe size differs from pinned ABI')
        identity=proof.parent.name
        if self.enabled and identity in self.recipes:
            if self.recipes[identity]!=recipe:raise ValueError('Conflicting native recipe identity')
        elif self.enabled and self.recipe_bytes+len(recipe)<=MAX_RECIPE_BYTES:
            self.recipes[identity]=recipe;self.recipe_bytes+=len(recipe)
        else:
            proof.mkdir(parents=True,exist_ok=True)
            (proof/'request.recipe').write_bytes(recipe)
        directory = self.directory if self.enabled else proof
        if not self.enabled:directory.mkdir(exist_ok=True)
        for code in (vs,ps):
            key = fnv64(code)
            self.report['bytecode_requests'] += 1
            if self.enabled and key in self.pool:
                if self.pool[key] != code:
                    raise ValueError('Conflicting bytecode at content key')
                self.report['verified_memory_hits'] += 1
                continue
            save_code(directory/f'code_{key:016x}.dxbc',code)
            self.report['file_checks_or_writes'] += 1
            if self.enabled and self.bytes+len(code)<=MAX_BYTES:
                self.pool[key]=code
                self.bytes+=len(code)
        self.report['retained_bytes']=self.bytes
        if not self.enabled:(proof/'result.json').write_text('{"pending":true}\n')

    def environment(self, env, root):
        if self.enabled:
            env.update(RSX_PSO_PREPARE_CODE_DIR=str(self.directory),
                       RSX_PSO_PREPARE_RESULTS=str(root/'batch-results.jsonl'),
                       RSX_PSO_PREPARE_REQUESTS=str(root/'batch-requests.bin'))
            if self.bundle:env['RSX_PSO_PREPARE_CODE_BUNDLE']=str(self.bundle)
        return env

    def recipe(self, root, identity):
        if identity in self.recipes:return self.recipes[identity]
        return bounded_read(root/identity/'pipeline/request.recipe',2760)

    def result(self, root, identity):
        if self.enabled:return self.results[identity]
        import json
        return json.loads(bounded_read(root/identity/'pipeline/result.json',65536))

    def finish(self):
        self.recipes.clear()
        self.recipe_bytes=0
        if self.bundle is not None:
            # Every owned native process has exited before results are consumed.
            # This transport is rebuilt on resume; it is never a shader cache.
            self.bundle.unlink()
            self.bundle=None

    def release(self, root=None, poll=None):
        # One private transient transport. Durable individual cache files are
        # still written/verified, so cancellation and older engines can resume.
        if self.code_enabled and root is not None and self.pool and len(self.pool)==self.report['file_checks_or_writes'] and len(self.pool)<=8192:
            root=Path(root);root.mkdir(parents=True,exist_ok=True)
            self.bundle=root/'bytecode-bundle.bin'
            offset=16+16*len(self.pool)
            with self.bundle.open('wb') as stream:
                stream.write(struct.pack('<8sII',b'GT5PCOD1',len(self.pool),self.bytes))
                for number,(key,code) in enumerate(self.pool.items()):
                    if poll and number%128==0:poll()
                    stream.write(struct.pack('<QII',key,len(code),offset));offset+=len(code)
                for number,code in enumerate(self.pool.values()):
                    if poll and number%128==0:poll()
                    stream.write(code)
            self.report['code_bundle_bytes']=offset
        self.report['code_bundle']=self.bundle is not None
        self.report['peak_recipe_bytes']=self.recipe_bytes
        self.report['recipe_byte_budget']=MAX_RECIPE_BYTES
        self.report['peak_verified_bytes']=self.bytes
        self.pool.clear()  # Durable shader checkpoints remain authoritative on resume.
        self.bytes=0
        self.report['retained_bytes']=0
