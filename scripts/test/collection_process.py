"""Real Windows private-job cancellation/timeout/owner-death guarantees."""
import ctypes
from pathlib import Path
import os
import subprocess
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).parents[1]))
from collection_process import run_owned

root=Path(__file__).parents[2]/'scratch'/('collection-job-'+uuid.uuid4().hex)
root.mkdir()
env=dict(os.environ)
assert 'guest entry was not executed' in run_owned([sys.executable,'-c',"print('guest entry was not executed')"],root,env,root/'normal.log')
try:run_owned([sys.executable,'-c',"print('guest entry was not executed');raise SystemExit(3)"],root,env,root/'failure.log')
except ValueError:pass
else:raise AssertionError('Failed child accepted')
try:run_owned([sys.executable,'-c','import time;time.sleep(60)'],root,env,root/'timeout.log',timeout=.1)
except TimeoutError:pass
else:raise AssertionError('Timeout ignored')
def cancel():raise KeyboardInterrupt('cancel')
try:run_owned([sys.executable,'-c','import time;time.sleep(60)'],root,env,root/'cancel.log',cancel)
except KeyboardInterrupt:pass
else:raise AssertionError('Cancellation ignored')
probe=root/'probe.py'
probe.write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\nPath(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(60)\n")
owner=root/'owner.py'
owner.write_text('from pathlib import Path\nimport os,sys\nsys.path.insert(0,sys.argv[1])\nfrom collection_process import run_owned\nrun_owned([sys.executable,sys.argv[2],sys.argv[3]],Path(sys.argv[4]),dict(os.environ),Path(sys.argv[4])/"owner.log")\n')
marker=root/'child.pid'
sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW)
parent=subprocess.Popen([sys.executable,str(owner),str(Path(__file__).parents[1]),str(probe),str(marker),str(root)],creationflags=subprocess.CREATE_NO_WINDOW)
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
kernel.CloseHandle.argtypes=[ctypes.c_void_p]
handle=None
try:
    start=time.monotonic()
    while not marker.exists():
        if parent.poll() is not None or time.monotonic()-start>15:raise AssertionError('Owned descendant did not start')
        time.sleep(.05)
    handle=kernel.OpenProcess(0x100000,False,int(marker.read_text()))
    assert handle
    parent.terminate();parent.wait(timeout=10)
    assert kernel.WaitForSingleObject(handle,10000)==0,'Descendant survived owner death'
    assert sentinel.poll() is None,'Unrelated process was stopped'
finally:
    if handle:kernel.CloseHandle(handle)
    if parent.poll() is None:parent.terminate();parent.wait(timeout=10)
    sentinel.terminate();sentinel.wait(timeout=10)
print('Owned offline child exit, rejection, timeout, cancellation and nested descendant cleanup on owner death passed')
