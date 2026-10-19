#!/usr/bin/env python3
"""Prepare only the rehearsal VMs for export, without a network interface.

Run on Proxmox AFTER qmrestore has completed successfully. Production IDs are
deliberately rejected. This never edits backup archives or production guests.
"""
import argparse
import json
import subprocess
import time


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def execute(vmid, program, timeout=120):
    result = json.loads(command("qm", "guest", "exec", vmid, "--timeout", str(timeout),
                                "--", "python3", "-c", program))
    if result.get("exitcode") != 0:
        raise RuntimeError("Guest preparation failed: " + result.get("err-data", "")[-1500:])
    return result.get("out-data", "")


def prepare(vmid):
    if vmid not in {"202", "203"}:
        raise ValueError("Only rehearsal VMs 202 and 203 are permitted")
    config = command("qm", "config", vmid)
    if any(line.startswith("lock:") for line in config.splitlines()):
        raise RuntimeError("Restore still locked; do not boot")
    if command("qm", "status", vmid).strip() != "status: stopped":
        raise RuntimeError("Expected a stopped restored guest")
    networks = [line.split(":", 1)[0] for line in config.splitlines()
                if line.startswith("net") and line.split(":", 1)[0][3:].isdigit()]
    args = ["qm", "set", vmid, "--onboot", "0", "--memory", "2048" if vmid == "202" else "4096",
            "--cores", "2", "--name", "dr-extract-db" if vmid == "202" else "dr-extract-app"]
    if networks:
        args += ["--delete", ",".join(networks)]
    command(*args)
    verified = command("qm", "config", vmid)
    assert not any(line.startswith("net") and line.split(":", 1)[0][3:].isdigit()
                   for line in verified.splitlines())
    command("qm", "start", vmid)
    for _ in range(120):
        try:
            command("qm", "agent", vmid, "ping")
            break
        except subprocess.CalledProcessError:
            time.sleep(3)
    else:
        raise RuntimeError("Guest agent not ready; guest remains isolated")
    # These service changes affect only the restored test guest with no NIC.
    execute(vmid, "import subprocess; subprocess.run(['systemctl','stop',"
            "'mielenosoitukset_fi','anal_aggregate','docker','postfix','dovecot'],"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)")
    if vmid == "202":
        program = '''
import hashlib,json,pathlib,subprocess
subprocess.run(['systemctl','stop','mongod'],check=True)
subprocess.run(['/usr/bin/mongod','--dbpath','/var/lib/mongodb','--bind_ip','127.0.0.1',
 '--port','27017','--noauth','--wiredTigerCacheSizeGB','0.5','--setParameter',
 'ttlMonitorEnabled=false','--fork','--logpath','/root/dr-restore-mongo.log'],check=True,
 stdout=subprocess.DEVNULL)
subprocess.run(['/usr/bin/mongodump','--host','127.0.0.1','--port','27017',
 '--db','mielenosoitukset','--gzip','--archive=/root/dr-mielenosoitukset.archive.gz'],
 check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
p=pathlib.Path('/root/dr-mielenosoitukset.archive.gz')
h=hashlib.sha256()
with p.open('rb') as f:
 for block in iter(lambda:f.read(1048576),b''): h.update(block)
print(json.dumps({'archive_bytes':p.stat().st_size,'sha256':h.hexdigest()}))
'''
    else:
        program = '''
import hashlib,json,pathlib,subprocess
root='/var/www/mielenosoitukset_fi'
sha=subprocess.check_output(['git','-c','safe.directory='+root,'-C',root,'rev-parse','HEAD'],text=True).strip()
subprocess.run(['git','-c','safe.directory='+root,'-C',root,'archive','--format=tar.gz',
 '-o','/root/dr-app.tar.gz','HEAD'],check=True)
p=pathlib.Path('/root/dr-app.tar.gz')
h=hashlib.sha256()
with p.open('rb') as f:
 for block in iter(lambda:f.read(1048576),b''): h.update(block)
print(json.dumps({'build_sha':sha,'archive_bytes':p.stat().st_size,
 'sha256':h.hexdigest()}))
'''
    print(execute(vmid, program, timeout=0), end="", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vmid", choices=["202", "203"])
    prepare(parser.parse_args().vmid)
