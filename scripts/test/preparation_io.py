"""Read pool bounds/order and joined cancellation, including retained tracebacks."""
import os
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
from preparation_io import read_pool,worker_count

for value in ('1','2','4'):assert worker_count({'GT5P_PREPARE_IO_WORKERS':value})==int(value)
assert worker_count({})==4
for value in ('','0','3','8',True):
    try:worker_count({'GT5P_PREPARE_IO_WORKERS':value})
    except ValueError:pass
    else:raise AssertionError('Invalid pool size accepted')

lock=threading.Lock();active=0;maximum=0;started=[];finished=[]
def read(number):
    global active,maximum
    with lock:
        active+=1;maximum=max(maximum,active);started.append(number)
    try:
        time.sleep(.01*(4-number%4))
        return number
    finally:
        with lock:active-=1;finished.append(number)

with read_pool(read,range(20),4) as results:assert list(results)==list(range(20))
assert 1<maximum<=4 and active==0 and len(started)==20

started.clear();finished.clear();caught=None
try:
    with read_pool(read,range(100),4) as results:
        assert next(results)==0
        assert len(started)<=4
        raise KeyboardInterrupt('owned cancellation')
except KeyboardInterrupt as error:caught=error
assert caught is not None and caught.__traceback__ is not None
assert active==0 and sorted(started)==sorted(finished) and len(started)<=4

def failed(number):
    if number==1:raise ValueError('read rejected')
    return read(number)
try:
    with read_pool(failed,range(100),4) as results:list(results)
except ValueError:pass
else:raise AssertionError('Read failure swallowed')
assert active==0

with read_pool(lambda n:n,range(10),1) as results:assert list(results)==list(range(10))
maximum=0
with read_pool(read,range(8),2) as results:assert list(results)==list(range(8))
assert 1<maximum<=2 and active==0
print('Bounded ordered read pool, invalid config, serialized rollback and joined cancellation/failure passed')
