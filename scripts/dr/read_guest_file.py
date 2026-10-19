#!/usr/bin/env python3
"""Stream a prepared archive through QEMU agent; restored guests need no NIC.

Run on Proxmox, pipe stdout directly into a private destination over SSH.
Only the two rehearsal guests and fixed archive paths are accepted.
"""
import base64
import json
import subprocess
import sys

ARCHIVES = {"202": "/root/dr-mielenosoitukset.archive.gz", "203": "/root/dr-app.tar.gz"}


def execute(vmid, program):
    result = subprocess.run(["qm", "guest", "exec", vmid, "--timeout", "120", "--",
                             "python3", "-c", program], capture_output=True, check=True)
    response = json.loads(result.stdout)
    if response.get("exitcode") != 0:
        raise RuntimeError("Guest export command failed")
    return response.get("out-data", "")


def stream(vmid):
    path = ARCHIVES[vmid]
    size = int(execute(vmid, f"import os; print(os.path.getsize({path!r}))"))
    for offset in range(0, size, 512 * 1024):
        code = (f"import base64; f=open({path!r},'rb'); f.seek({offset}); "
                "print(base64.b64encode(f.read(524288)).decode())")
        chunk = base64.b64decode(execute(vmid, code), validate=False)
        expected = min(524288, size - offset)
        if len(chunk) != expected:
            raise RuntimeError("Truncated QEMU guest export")
        sys.stdout.buffer.write(chunk)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ARCHIVES:
        raise SystemExit("Usage: read_guest_file.py {202|203}")
    stream(sys.argv[1])
