"""
Generate synthetic benchmark traces for 20 and 24 RMs in all 5 formats
(VEA, V, VpEA, EA, E), suitable for the precision experiment.

Each trace represents a clean, valid 2PC execution:
  - all RMs prepare sequentially
  - TM receives each Prepared message (with one stuttering receipt)
  - TM commits
  - all RMs receive Commit

The 5 formats mirror the logging levels used in the original benchmarks:
  VEA  = state variable updates + event name + event args
  V    = state variable updates only
  VpEA = state variable updates + event name (TM actions only), no event args
  EA   = event name + event args only (no state updates)
  E    = event name only
"""

import json
import os
from pathlib import Path

BM_DIR = Path(__file__).parent / "BenchMarks"


def rm_name(i):
    return f"rm-{i}"


STUTTERS = 3  # TMRcvPrepared steps per RM (~3.56 in the real 16RM benchmark trace)


def generate_vea(rms):
    lines = []
    for i, rm in enumerate(rms):
        lines.append({
            "msgs": [{"op": "AddElement", "path": [], "args": [{"type": "Prepared", "rm": rm}]}],
            "rmState": [{"op": "Update", "path": [rm], "args": ["prepared"]}],
            "event": "RMPrepare",
            "event_args": [rm],
        })
        for _ in range(STUTTERS):
            lines.append({"tmPrepared": [{"op": "AddElement", "path": [], "args": [rm]}], "event": "TMRcvPrepared"})
    lines.append({"msgs": [{"op": "AddElement", "path": [], "args": [{"type": "Commit"}]}], "event": "TMCommit"})
    for rm in rms:
        lines.append({
            "rmState": [{"op": "Update", "path": [rm], "args": ["committed"]}],
            "event": "RMRcvCommitMsg",
            "event_args": [rm],
        })
    return lines


def generate_v(rms):
    lines = []
    for rm in rms:
        lines.append({
            "msgs": [{"op": "AddElement", "path": [], "args": [{"type": "Prepared", "rm": rm}]}],
            "rmState": [{"op": "Update", "path": [rm], "args": ["prepared"]}],
        })
        for _ in range(STUTTERS):
            lines.append({"tmPrepared": [{"op": "AddElement", "path": [], "args": [rm]}]})
    lines.append({"msgs": [{"op": "AddElement", "path": [], "args": [{"type": "Commit"}]}]})
    for rm in rms:
        lines.append({"rmState": [{"op": "Update", "path": [rm], "args": ["committed"]}]})
    return lines


def generate_vpea(rms):
    lines = []
    for rm in rms:
        lines.append({
            "msgs": [{"op": "AddElement", "path": [], "args": [{"type": "Prepared", "rm": rm}]}],
            "rmState": [{"op": "Update", "path": [rm], "args": ["prepared"]}],
        })
        for _ in range(STUTTERS):
            lines.append({"tmPrepared": [{"op": "AddElement", "path": [], "args": [rm]}], "event": "TMRcvPrepared"})
    lines.append({"msgs": [{"op": "AddElement", "path": [], "args": [{"type": "Commit"}]}], "event": "TMCommit"})
    for rm in rms:
        lines.append({"rmState": [{"op": "Update", "path": [rm], "args": ["committed"]}]})
    return lines


def generate_ea(rms):
    lines = []
    for rm in rms:
        lines.append({"event": "RMPrepare", "event_args": [rm]})
        for _ in range(STUTTERS):
            lines.append({"event": "TMRcvPrepared"})
    lines.append({"event": "TMCommit"})
    for rm in rms:
        lines.append({"event": "RMRcvCommitMsg", "event_args": [rm]})
    return lines


def generate_e(rms):
    lines = []
    for rm in rms:
        lines.append({"event": "RMPrepare"})
        for _ in range(STUTTERS):
            lines.append({"event": "TMRcvPrepared"})
    lines.append({"event": "TMCommit"})
    for rm in rms:
        lines.append({"event": "RMRcvCommitMsg"})
    return lines


def write_ndjson(path, lines):
    with open(path, "w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    print(f"  Written: {path.name} ({len(lines)} lines)")


def write_conf(n):
    rms = [rm_name(i) for i in range(n)]
    conf_path = BM_DIR / f"conf.{n}RM.ndjson"
    with open(conf_path, "w") as f:
        f.write(json.dumps({"RM": rms}) + "\n")
        f.write(json.dumps({"TM": ["tm"]}) + "\n")
    print(f"  Written: {conf_path.name}")
    return rms


GENERATORS = {
    "VEA": generate_vea,
    "V":   generate_v,
    "VpEA": generate_vpea,
    "EA":  generate_ea,
    "E":   generate_e,
}

for n in [20, 24]:
    print(f"\n=== {n} RMs ===")
    rms = write_conf(n)
    for cfg, gen_fn in GENERATORS.items():
        trace_path = BM_DIR / f"trace.ndjson.{n}RM.{cfg}"
        write_ndjson(trace_path, gen_fn(rms))

print("\nDone.")
