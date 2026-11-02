"""Sequential manifests within the unchanged native 4,096-request budget.

The caller owns the preparation lock and process job. Proof directories remain
under the same root; only the owned jobs.txt manifest is replaced between runs.
"""
import re

MAX_REQUESTS = 4096
SUMMARY = re.compile(r'\[pso-material-batch\] valid=1 requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)')


def run_batches(requests, root, engine, game_root, env, log_path, runner, progress=None):
    if len(set(requests)) != len(requests) or any(not re.fullmatch('[0-9a-f]{64}', identity) for identity in requests):
        raise ValueError('Invalid/duplicate native request identity')
    counts = [0, 0, 0, 0]
    for start in range(0, len(requests), MAX_REQUESTS):
        chunk = requests[start:start + MAX_REQUESTS]
        if progress:
            progress(start, len(requests))
        (root/'jobs.txt').write_text(''.join(identity+'\n' for identity in chunk), encoding='ascii')
        path = log_path if start == 0 else log_path.with_name(f'{log_path.stem}-{start // MAX_REQUESTS:04d}{log_path.suffix}')
        log = runner(engine, game_root, env, path, timeout=900)
        matches = SUMMARY.findall(log)
        if len(matches) != 1 or list(map(int, matches[0][:2])) != [len(chunk)] * 2:
            raise ValueError('Native batch completion was not confirmed')
        values = list(map(int, matches[0]))
        if not 0 <= values[3] <= values[2]:
            raise ValueError('Invalid native batch driver counts')
        counts = [a+b for a, b in zip(counts, values)]
    return counts
