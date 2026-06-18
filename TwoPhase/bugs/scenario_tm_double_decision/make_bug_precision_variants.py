"""
Derive the 5 trace-precision variants (VEA, V, VpEA, EA, E) of the
double-decision bug trace from the full (VEA) trace, by field-stripping.

Precision levels (cf. paper Sect. 4.5):
  VEA  - all variables + event name + event args
  V    - variables only (no event name / args)
  VpEA - variables always + events/args only for the TM's actions
  EA   - event name + args only (no variable updates)
  E    - event name only

Run from the scenario folder; reads trace.ndjson.BUG-4RM.VEA, writes the
other four next to it.
"""
import ndjson
import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "trace.ndjson.BUG-4RM.VEA"

VAR_KEYS = {"msgs", "rmState", "tmState", "tmPrepared"}
TM_EVENTS = {"TMCommit", "TMAbort", "TMRcvPrepared"}


def normalize(line):
    """tracer emits 'desc':'rm-0'; the spec reads 'event_args':['rm-0']."""
    line = dict(line)
    if "desc" in line:
        line["event_args"] = [line.pop("desc")]
    return line


def project(line, keep_vars, keep_event, keep_args):
    out = {}
    if keep_vars:
        out.update({k: v for k, v in line.items() if k in VAR_KEYS})
    if keep_event and "event" in line:
        out["event"] = line["event"]
        if keep_args and "event_args" in line:
            out["event_args"] = line["event_args"]
    return out


def main():
    lines = [normalize(l) for l in ndjson.load(open(SRC))]

    def emit(suffix, fn):
        out = [fn(l) for l in lines]
        dst = HERE / f"trace.ndjson.BUG-4RM.{suffix}"
        with open(dst, "w") as f:
            ndjson.dump(out, f)
        print(f"  wrote {dst.name}")

    emit("VEA",  lambda l: project(l, True,  True,  True))
    emit("V",    lambda l: project(l, True,  False, False))
    emit("EA",   lambda l: project(l, False, True,  True))
    emit("E",    lambda l: project(l, False, True,  False))
    # VpEA: variables always; event+args only for TM actions
    emit("VpEA", lambda l: {
        **project(l, True, False, False),
        **(project(l, False, True, True) if l.get("event") in TM_EVENTS else {}),
    })


if __name__ == "__main__":
    main()
