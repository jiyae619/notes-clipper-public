"""Run a command with iCloud's "download on read" turned on.

With Optimize Mac Storage, iCloud offloads files you haven't opened lately and
leaves a placeholder. Opening one from Terminal downloads it; opening one from
a launchd job fails with EDEADLK ("Resource deadlock avoided"), because
background processes aren't allowed to trigger downloads by default. On
2026-11-13 that stopped a run: three topic notes were offloaded, so routing
couldn't read them and the page rebuild failed.

This sets the process policy that allows it, then execs the command. The
policy carries over to the command and everything it starts. If it can't be
set (not macOS, older macOS), the command still runs as before.

    python3 materialize.py /bin/bash process_inbox.sh
"""
import ctypes, os, sys

IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES = 3
IOPOL_SCOPE_PROCESS = 0
IOPOL_MATERIALIZE_DATALESS_FILES_ON = 2

try:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.setiopolicy_np(IOPOL_TYPE_VFS_MATERIALIZE_DATALESS_FILES, IOPOL_SCOPE_PROCESS,
                           IOPOL_MATERIALIZE_DATALESS_FILES_ON) != 0:
        print(f"materialize: couldn't allow iCloud downloads (errno {ctypes.get_errno()})", file=sys.stderr)
except (OSError, AttributeError):
    pass
os.execv(sys.argv[1], sys.argv[1:])
