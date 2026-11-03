"""Owned, atomically checkpointed offline preparation; no cache removal."""
import json
import os
from pathlib import Path

from pipeline_catalogue_limits import MAX_RECORDS
from shader_coverage import bounded_read
from train_pipeline_cache import save_report

# Measured shape of one prepared record, rounded up from a completed generation:
# requests/<id>/pipeline holds the recipe, two bytecode files and the result
# (6 entries), and the selected extra translation repeats that shape (7).
# The shader cache holds about five more entries per record outside warmup.
# Warmup follows the runtime recipe cap: one recipe file and one bytecode file.
_RECORD_ENTRIES = 6 + 7 + 5
_WARMUP_ENTRIES = 8192 * 2
_GENERATION_OVERHEAD = 256


def generation_entry_budget(records=MAX_RECORDS):
    """Directory entries one preparation generation is allowed to contain."""
    if type(records) is not int or records < 1 or records > MAX_RECORDS:
        raise ValueError('Preparation entry budget requires a catalogue-sized record count')
    return _GENERATION_OVERHEAD + _WARMUP_ENTRIES + records * _RECORD_ENTRIES


OUTPUT_ENTRY_BUDGET = generation_entry_budget()


def preflight_tree(root, budget=OUTPUT_ENTRY_BUDGET):
    stack=[root];visited=0
    while stack:
        folder=stack.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                visited+=1
                if visited>budget:raise ValueError('Preparation output entry budget exceeded')
                info=entry.stat(follow_symlinks=False)
                if entry.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
                    raise ValueError('Redirected preparation output is not writable: '+entry.path)
                if entry.is_dir(follow_symlinks=False):stack.append(Path(entry.path))
                # Windows DirEntry.stat can report zero links; Path.stat queries
                # the file handle and supplies the real hard-link count.
                elif Path(entry.path).stat().st_nlink>1:
                    raise ValueError('Hard-linked preparation output is not writable: '+entry.path)


class Checkpoint:
    def __init__(self,output,contract,resume=False,progress=None):
        self.output=output
        self.contract=contract
        self.resume=resume
        self.stream=None
        self.state=None
        self.progress=progress

    def __enter__(self):
        if self.resume:
            if not self.output.is_dir():raise ValueError('Resume requires an existing preparation checkpoint')
        else:
            self.output.mkdir(parents=True)
        lock=self.output/'preparation.lock'
        if lock.exists() or lock.is_symlink():
            info=lock.stat(follow_symlinks=False)
            if lock.is_symlink() or getattr(info,'st_file_attributes',0)&0x400 or info.st_nlink>1:
                raise ValueError('Redirected/hard-linked preparation lock is not writable')
        self.stream=lock.open('a+b')
        try:
            if self.stream.seek(0,2)==0:
                self.stream.write(b'\0');self.stream.flush()
            self.stream.seek(0)
            try:
                if os.name=='nt':
                    import msvcrt
                    msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(self.stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError('Another preparation owns this output; nothing was stopped') from exc
            if self.resume:
                preflight_tree(self.output)
                try:self.state=json.loads(bounded_read(self.output/'preparation-state.json',65536))
                except (ValueError,OSError) as exc:
                    raise ValueError('Missing/malformed preparation checkpoint; cache preserved') from exc
                if (not isinstance(self.state,dict) or set(self.state)-{'schema','contract','attempt','phase','progress','error'} or
                        type(self.state.get('schema')) is not int or self.state.get('schema')!=1 or self.state.get('contract')!=self.contract or
                        type(self.state.get('attempt')) is not int or not 1<=self.state['attempt']<1000000):
                    raise ValueError('Preparation checkpoint contract/version mismatch; cache preserved')
                self.state['attempt']+=1
            else:
                self.state=dict(schema=1,contract=self.contract,attempt=1,phase='starting',progress={})
            return self
        except BaseException:
            self.stream.close();self.stream=None
            raise

    def stage(self,phase,**progress):
        if self.progress:self.progress(phase,progress)
        self.state.update(phase=phase,progress=progress)
        self.state.pop('error',None)
        save_report(self.output/'preparation-state.json',self.state)

    def __exit__(self,kind,value,traceback):
        try:
            if kind is not None:
                self.state.update(phase='interrupted' if issubclass(kind,KeyboardInterrupt) else 'failed',error=str(value)[:1000])
                save_report(self.output/'preparation-state.json',self.state)
        finally:
            self.stream.close();self.stream=None
        return False
