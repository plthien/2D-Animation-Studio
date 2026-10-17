import pytest
from app.animation.strict_json import parse_strict_document
from app.animation.service import DomainError
from app.animation.process.host_owned_process import HostOwnedProcess

def test_strict_json_duplicate_keys_and_nonfinite():
    assert parse_strict_document('{"valid":true}')=={"valid":True}
    for text in ('{"a":1,"a":2}', '{"value":NaN}', '[1]', 'not JSON'):
        with pytest.raises(DomainError):
            parse_strict_document(text)

def test_strict_json_bounded_size():
    with pytest.raises(DomainError) as got:
        parse_strict_document('{"x":"12345"}', max_bytes=6)
    assert got.value.code=="IMPORT_TOO_LARGE"

def test_process_owner_importable_without_legacy():
    assert HostOwnedProcess.__module__.startswith("app.animation.process.")


def test_windows_job_object_configure_assign_terminate_close_and_idempotent():
    """Fake Win32 DLL tests the exact limit flag and owned-handle lifecycle."""
    import ctypes
    from ctypes import wintypes
    from app.animation.process.windows_job_object import (
        WindowsJobObject, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        _JobObjectExtendedLimitInformation,
    )

    class FakeKernel32:
        def __init__(self):
            self.calls=[]
        def GetCurrentProcess(self):
            return 1
        def CreateJobObjectW(self,*args):
            self.calls.append(("create",))
            return 101
        def SetInformationJobObject(self,handle,info_class,ptr,size):
            flags=ctypes.cast(ptr,ctypes.POINTER(_JobObjectExtendedLimitInformation)).contents.BasicLimitInformation.LimitFlags
            self.calls.append(("set",handle,info_class,flags,size))
            return 1
        def AssignProcessToJobObject(self,handle,process):
            self.calls.append(("assign",handle,process.value))
            return 1
        def TerminateJobObject(self,handle,exit_code):
            self.calls.append(("terminate",handle,exit_code))
            return 1
        def CloseHandle(self,handle):
            self.calls.append(("close",handle))
            return 1
    kernel=FakeKernel32()
    job=WindowsJobObject(kernel32=kernel)
    job.assign_process_handle(201)
    job.terminate(exit_code=7)
    job.close()
    job.close()
    assert [x[0] for x in kernel.calls]==["create","set","assign","terminate","close"]
    assert kernel.calls[1][3]==JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    assert kernel.calls[2][2]==201
    assert kernel.calls[3][2]==7


def test_process_job_assignment_failure_kills_child_and_closes_handle(tmp_path):
    import os
    import subprocess
    import sys
    class BrokenJob:
        def __init__(self):
            self.closed=False
        def assign_process(self,process):
            raise OSError("Injected AssignProcessToJobObject failure")
        def close(self):
            self.closed=True
    state={}
    def make_job():
        state["job"]=BrokenJob()
        return state["job"]
    process_holder={}
    def make_process(*args,**kwargs):
        p=subprocess.Popen(*args,**kwargs)
        process_holder["child"]=p
        return p
    with pytest.raises(OSError,match="Injected"):
        HostOwnedProcess.start(
            [sys.executable,"-c","import time; time.sleep(60)"],
            cwd=tmp_path,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            bufsize=0,env=dict(os.environ),popen_factory=make_process,
            job_factory=make_job,use_job_object=True,
        )
    assert state["job"].closed
    assert process_holder["child"].poll() is not None


def test_real_windows_job_owns_descendant_tree_without_killing_unrelated(tmp_path):
    """A separate OS process bounds native Job Object waits and owns child cleanup.

    The unrelated process is created by the outer test and cannot be killed by
    the inner Job; the worker's crash closes its Job handle by Windows design.
    """
    import ctypes
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path
    if os.name != "nt":
        pytest.skip("Windows-only functional ownership gate; always runs on windows-latest")

    if os.environ.get("C2_JOB_CHILD_TEST") != "1":
        unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"],
            cwd=tmp_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            env=dict(os.environ)
            env["C2_JOB_CHILD_TEST"]="1"
            env["C2_JOB_UNRELATED_PID"]=str(unrelated.pid)
            run=subprocess.run([sys.executable,"-m","pytest","-q","-s",
                str(Path(__file__).resolve())+"::test_real_windows_job_owns_descendant_tree_without_killing_unrelated"],
                cwd=Path(__file__).resolve().parents[2],env=env,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=25)
            assert run.returncode==0, run.stdout+"\n"+run.stderr
            assert unrelated.poll() is None, "Unrelated process killed by Job Object"
        finally:
            if unrelated.poll() is None:
                unrelated.kill()
            unrelated.wait(timeout=5)
        return

    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint]
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    kernel.WaitForSingleObject.restype=ctypes.c_uint
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    kernel.CloseHandle.restype=ctypes.c_int

    def alive(pid):
        handle=kernel.OpenProcess(0x00100000,False,pid)
        if not handle:
            return False
        try:
            return kernel.WaitForSingleObject(handle,0)==258
        finally:
            kernel.CloseHandle(handle)

    gate=tmp_path/"spawn-now"
    child_file=tmp_path/"descendant-pid.txt"
    parent_code=(
        "import sys,subprocess,time,pathlib;"
        "g=pathlib.Path(sys.argv[1]);o=pathlib.Path(sys.argv[2]);"
        "\nwhile not g.exists():time.sleep(.02)"
        "\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "o.write_text(str(p.pid));time.sleep(60)"
    )
    owned=None
    try:
        owned=HostOwnedProcess.start(
            [sys.executable,"-c",parent_code,str(gate),str(child_file)],
            cwd=tmp_path,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            bufsize=0,env=dict(os.environ),use_job_object=True)
        assert owned.owns_process_tree
        gate.write_text("ok")
        deadline=time.monotonic()+10
        while not child_file.exists() and time.monotonic()<deadline:
            time.sleep(.05)
        assert child_file.exists(),"Owned parent did not start its child"
        descendant=int(child_file.read_text())
        assert alive(owned.pid) and alive(descendant)
        unrelated_pid=int(os.environ["C2_JOB_UNRELATED_PID"])
        assert alive(unrelated_pid)
        owned.release()
        owned.release()
        deadline=time.monotonic()+7
        while (alive(owned.pid) or alive(descendant)) and time.monotonic()<deadline:
            time.sleep(.05)
        assert not alive(owned.pid),"Owned parent remains alive"
        assert not alive(descendant),"Owned descendant remains alive"
        assert alive(unrelated_pid),"Unrelated process killed"
    finally:
        if owned is not None:
            owned.release()
            try: owned.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                owned.process.kill()
                owned.process.wait(timeout=3)
