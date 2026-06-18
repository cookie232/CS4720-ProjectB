"""
Run TLC on the double-decision bug trace across all trace-precision
configurations (VEA, V, VpEA, EA, E), in both BFS and DFS, and report
whether trace validation DETECTS the bug plus the search cost.

Counterpart to ../../run_precision_experiment.py, but for an *invalid*
(buggy) trace: success here means TLC REJECTS the trace
(TraceAccepted = FALSE), i.e. the bug is caught.

Prereq: the precision variants must exist (run make_bug_precision_variants.py).
"""
import csv
import os
import re
import subprocess
from pathlib import Path

HERE   = Path(__file__).parent
BASE   = HERE.parent.parent                       # the TwoPhase/ dir
SPEC   = str(BASE / "spec" / "TwoPhaseTrace.tla")
CONF   = str(BASE / "BenchMarks" / "conf.4RM.ndjson")
OUTDIR = HERE / "precision_results"
TLA_CP = os.pathsep.join([
    str(BASE.parent / "tools" / "tla2tools.jar"),
    str(BASE.parent / "tools" / "CommunityModules-deps.jar"),
])

CFGS = ["VEA", "V", "VpEA", "EA", "E"]
INFO = {  # what each precision level records (for the printed table)
    "VEA":  "vars + event + args",
    "V":    "variables only",
    "VpEA": "vars + TM events",
    "EA":   "event + args only",
    "E":    "event names only",
}


def build_cmd(dfs):
    cmd = ["java", "-XX:+UseParallelGC"]
    if dfs:
        cmd.append("-Dtlc2.tool.queue.IStateQueue=StateDeque")
    cmd += ["-cp", TLA_CP, "tlc2.TLC", "-note", SPEC]
    return cmd


def run_tlc(trace, dfs):
    env = os.environ.copy()
    env["TRACE_PATH"]  = str(trace)
    env["CONFIG_PATH"] = CONF
    proc = subprocess.run(build_cmd(dfs), env=env, cwd=str(BASE),
                          capture_output=True, text=True)
    return proc.stdout + proc.stderr


def parse(out):
    if re.search(r"TraceAccepted.*is false", out):
        verdict = "DETECTED"          # spec rejected the buggy trace -> good
    elif "No error has been found" in out:
        verdict = "ACCEPTED(!)"       # spec accepted a buggy trace -> false negative
    else:
        verdict = "UNKNOWN"
    m  = re.search(r"([\d,]+) distinct states found", out)
    distinct = int(m.group(1).replace(",", "")) if m else None
    m2 = re.search(r"depth of the complete state graph search is (\d+)", out)
    depth = int(m2.group(1)) if m2 else None
    m3 = re.search(r'event \|-> "(\w+)"', out)   # the trace event that could not match
    fail_at = m3.group(1) if m3 else None
    return verdict, distinct, depth, fail_at


def main():
    OUTDIR.mkdir(exist_ok=True)
    rows = []

    hdr = f"{'Config':<6} {'Records':<20} {'Mode':<4} {'Verdict':<11} {'Distinct':>9} {'Depth':>6} {'FailsAt':>9}"
    print(hdr)
    print("-" * len(hdr))

    for cfg in CFGS:
        trace = HERE / f"trace.ndjson.BUG-4RM.{cfg}"
        if not trace.exists():
            print(f"  SKIP (missing {trace.name}) — run make_bug_precision_variants.py first")
            continue
        for dfs in (False, True):
            mode = "DFS" if dfs else "BFS"
            out = run_tlc(trace, dfs)
            (OUTDIR / f"BUG-4RM-{cfg}-{mode}.txt").write_text(out)
            verdict, distinct, depth, fail_at = parse(out)
            rows.append(dict(cfg=cfg, records=INFO[cfg], mode=mode, verdict=verdict,
                             distinct=distinct, depth=depth, fail_at=fail_at))
            print(f"{cfg:<6} {INFO[cfg]:<20} {mode:<4} {verdict:<11} "
                  f"{str(distinct or '—'):>9} {str(depth or '—'):>6} {str(fail_at or '—'):>9}")

    # Compact BFS/DFS summary
    print("\n" + "=" * 56)
    print("SUMMARY — double-decision bug detection vs trace precision")
    print("=" * 56)
    print(f"{'Config':<6} {'Records':<20} {'Detected?':<10} {'Distinct (BFS/DFS)':>18}")
    print("-" * 56)
    for cfg in CFGS:
        b = next((r for r in rows if r["cfg"] == cfg and r["mode"] == "BFS"), None)
        d = next((r for r in rows if r["cfg"] == cfg and r["mode"] == "DFS"), None)
        if not b:
            continue
        det = "yes" if b["verdict"] == "DETECTED" and d["verdict"] == "DETECTED" else "NO"
        cell = f"{b['distinct']}/{d['distinct']}"
        print(f"{cfg:<6} {INFO[cfg]:<20} {det:<10} {cell:>18}")

    csv_path = OUTDIR / "bug_precision_summary.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["cfg", "records", "mode", "verdict",
                                          "distinct", "depth", "fail_at"])
        w.writeheader()
        w.writerows(rows)
    print(f"\nRaw TLC logs: {OUTDIR}")
    print(f"CSV summary:  {csv_path}")


if __name__ == "__main__":
    main()
