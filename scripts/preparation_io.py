"""Ordered, bounded read-only work inside one owned preparation operation.

Only four requests may be outstanding (plus the result being consumed), rather
than Executor.map's unbounded prefetch. Workers never publish files or call UI callbacks.
Exit joins every submitted read before the caller releases its checkpoint lock.
"""
from collections import deque
from contextlib import closing, contextmanager
from concurrent.futures import ThreadPoolExecutor
import os


def worker_count(environ=None):
    value=(os.environ if environ is None else environ).get('GT5P_PREPARE_IO_WORKERS','4')
    if value not in ('1','2','4'):
        raise ValueError('GT5P_PREPARE_IO_WORKERS must be unset, 1, 2, or 4')
    return int(value)


def ordered_reads(function, items, workers=None):
    count=worker_count() if workers is None else workers
    if type(count) is not int or count not in (1,2,4):
        raise ValueError('Preparation I/O worker cap exceeded')
    if count==1:
        for item in items:yield function(item)
        return
    # Native checksum setup must finish on the owner before any worker uses it.
    from cache_hash import statistics
    statistics()
    pending=deque();iterator=iter(items)
    pool=ThreadPoolExecutor(max_workers=count,thread_name_prefix='prepare-read')
    try:
        for _ in range(count):
            try:item=next(iterator)
            except StopIteration:break
            pending.append(pool.submit(function,item))
        while pending:
            future=pending.popleft()
            yield future.result()
            # Refill only after the consumer processes the preceding result.
            try:item=next(iterator)
            except StopIteration:continue
            pending.append(pool.submit(function,item))
    finally:
        for future in pending:future.cancel()
        pool.shutdown(wait=True,cancel_futures=True)


@contextmanager
def read_pool(function,items,workers=None):
    # Explicit close matters: an exception traceback can retain a caller's
    # generator frame. Join before propagating it or publishing a handoff.
    with closing(ordered_reads(function,items,workers)) as results:
        yield results
