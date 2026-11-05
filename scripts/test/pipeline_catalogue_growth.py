"""Large metadata round trip and sequential native manifest boundary checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parents[1]))
import pipeline_template as t
import pipeline_contribution as c
from pipeline_native_batch import run_batches

baseline = t.read(Path(__file__).parents[2]/'assets/pipeline-templates/gt5p-disc-v2')
record = baseline['records'][0]
# Distinct numeric inputs exercise canonical catalogue identities, not native keys.
from pipeline_template_inputs import identity
records = []
for i in range(8193):
    row = copy.deepcopy(record)
    row['state']['ghi'] = i
    row['key'] = identity(row)
    records.append(row)
document = dict(baseline, records=records)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    t.bundle(copy.deepcopy(document), root/'bundle')
    assert len(json.loads((root/'bundle/index.json').read_text())['parts']) == 65
    assert b'\r\n' not in (root/'bundle/index.json').read_bytes()
    assert t.read(root/'bundle') == document
    try:
        c.encode(document)
    except ValueError:
        pass
    else:
        raise AssertionError('Large catalogue accepted as one collection session')
    requests = [f'{i+1:064x}' for i in range(8500)]
    calls = []
    def runner(engine, game_root, env, log, timeout):
        chunk = (root/'jobs.txt').read_text().splitlines()
        assert len(chunk) <= 4096 and timeout == 900
        calls.append((chunk, log.name))
        return f'[pso-material-batch] valid=1 requests={len(chunk)} created={len(chunk)} driver_calls={len(chunk)} cached_blob_calls=0'
    counts = run_batches(requests, root, None, None, {}, root/'native.log', runner)
    assert counts == [8500, 8500, 8500, 0]
    assert [len(chunk) for chunk, _ in calls] == [4096, 4096, 308]
    assert [key for chunk, _ in calls for key in chunk] == requests
    assert [log for _, log in calls] == ['native.log', 'native-0001.log', 'native-0002.log']
    calls.clear()
    def cancel(done, total):
        if done:
            raise InterruptedError('cancel after completed chunk')
    try:
        run_batches(requests, root, None, None, {}, root/'native.log', runner, cancel)
    except InterruptedError:
        pass
    else:
        raise AssertionError('Cancellation ignored')
    assert len(calls) == 1
    def invalid(*args, **kwargs):
        return '[pso-material-batch] valid=1 requests=4096 created=0 driver_calls=0 cached_blob_calls=0'
    try:
        run_batches(requests, root, None, None, {}, root/'native.log', invalid)
    except ValueError:
        pass
    else:
        raise AssertionError('Incomplete native batch accepted')
print('8193 metadata rows / 65 shards round-trip; collection budget preserved; 8500 native requests partition exactly; cancellation/failure stop safely')
