"""
Run TLC precision experiment for 20 and 24 RMs (extension beyond paper's range).
Uses the same infrastructure as run_precision_experiment.py.
"""
import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BASE      = Path(__file__).parent
SPEC      = str(BASE / "spec" / "TwoPhaseTrace.tla")
BM_DIR    = BASE / "BenchMarks"
OUT_DIR   = BASE / "results" / "precision_extension"
TLA_CP    = (
    str(BASE.parent / "tools" / "tla2tools.jar") + ";" +
    str(BASE.parent / "tools" / "CommunityModules-deps.jar")
)

RM_COUNTS = [20, 24]
CFGS      = ["VEA", "V", "VpEA", "EA", "E"]

BFS_TIMEOUT = 300   # 5 min
DFS_TIMEOUT = 120   # 2 min


def build_cmd(dfs: bool) -> list:
    cmd = ["java", "-XX:+UseParallelGC"]
    if dfs:
        cmd.append("-Dtlc2.tool.queue.IStateQueue=StateDeque")
    cmd += ["-cp", TLA_CP, "tlc2.TLC", "-note", SPEC]
    return cmd


def run_tlc(trace: Path, conf: Path, dfs: bool) -> tuple:
    env = os.environ.copy()
    env["TRACE_PATH"] = str(trace)
    env["CONFIG_PATH"] = str(conf)
    timeout = DFS_TIMEOUT if dfs else BFS_TIMEOUT
    t0 = time.time()
    proc = subprocess.Popen(
        build_cmd(dfs), env=env, cwd=str(BASE),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return stdout.decode(errors="replace") + stderr.decode(errors="replace"), time.time() - t0, False
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        return "", time.time() - t0, True


def parse(output: str) -> dict:
    verdict = (
        "OK"      if "No error has been found" in output else
        "ERROR"   if re.search(r"Error:|Assumption", output) else
        "UNKNOWN"
    )
    m = re.search(r"([\d,]+) states generated, ([\d,]+) distinct states found", output)
    states   = int(m.group(1).replace(",", "")) if m else None
    distinct = int(m.group(2).replace(",", "")) if m else None
    m2 = re.search(r"depth of the complete state graph search is (\d+)", output)
    depth = int(m2.group(1)) if m2 else None
    return dict(verdict=verdict, states=states, distinct=distinct, depth=depth)


OUT_DIR.mkdir(parents=True, exist_ok=True)
csv_path = OUT_DIR / "summary.csv"
rows = []

hdr = f"{'Instance':<16} {'Mode':<4} {'Verdict':<8} {'States':>9} {'Distinct':>9} {'Depth':>6} {'Time':>7}"
print(hdr)
print("-" * len(hdr))

for rm in RM_COUNTS:
    for cfg in CFGS:
        trace = BM_DIR / f"trace.ndjson.{rm}RM.{cfg}"
        conf  = BM_DIR / f"conf.{rm}RM.ndjson"
        if not trace.exists():
            print(f"  SKIP (trace not found): {trace.name}")
            continue

        for dfs in [False, True]:
            mode  = "DFS" if dfs else "BFS"
            label = f"TP {rm}RM {cfg}"

            raw_file = OUT_DIR / f"{rm}RM-{cfg}-{mode}.txt"
            if raw_file.exists():
                output = raw_file.read_text()
                elapsed = 0.0
                timed_out = ("TIMEOUT" in output or output.strip() == "")
                print(f"  SKIP (already done): {label} {mode}")
            else:
                print(f"  Running {label} {mode} ...", end="", flush=True)
                output, elapsed, timed_out = run_tlc(trace, conf, dfs)
                raw_file.write_text(output)

            if timed_out:
                row = dict(rm=rm, cfg=cfg, mode=mode, verdict="TIMEOUT",
                           states=None, distinct=None, depth=None, elapsed=round(elapsed, 1))
                print(f" TIMEOUT ({elapsed:.0f}s)")
            else:
                m = parse(output)
                row = dict(rm=rm, cfg=cfg, mode=mode, verdict=m["verdict"],
                           states=m["states"], distinct=m["distinct"], depth=m["depth"],
                           elapsed=round(elapsed, 1))
                print(f" {m['verdict']:<7} distinct={m['distinct']}, depth={m['depth']}, {elapsed:.1f}s")

            rows.append(row)
            dist_str = f"{row['distinct']:,}" if row["distinct"] else row["verdict"]
            print(f"{'':>2}{label:<16} {mode:<4} {row['verdict']:<8} "
                  f"{str(row['states'] or ''):>9} {dist_str:>9} "
                  f"{str(row['depth'] or ''):>6} {elapsed:>6.1f}s")

with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["rm","cfg","mode","verdict","states","distinct","depth","elapsed"])
    w.writeheader()
    w.writerows(rows)

print("\n" + "=" * 70)
print("SUMMARY — Distinct states (BFS / DFS)")
print("=" * 70)
print(f"{'Instance':<16}", end="")
for cfg in CFGS:
    print(f"  {cfg:>14}", end="")
print()
print("-" * (16 + 16 * len(CFGS)))

for rm in RM_COUNTS:
    print(f"TP {rm}RM{'':<8}", end="")
    for cfg in CFGS:
        bfs_row = next((r for r in rows if r["rm"]==rm and r["cfg"]==cfg and r["mode"]=="BFS"), None)
        dfs_row = next((r for r in rows if r["rm"]==rm and r["cfg"]==cfg and r["mode"]=="DFS"), None)
        def fmt(r):
            if r is None: return "—"
            if r["verdict"] == "TIMEOUT": return "∞"
            return f"{r['distinct']:,}" if r["distinct"] else "?"
        cell = f"{fmt(bfs_row)}/{fmt(dfs_row)}"
        print(f"  {cell:>14}", end="")
    print()

print(f"\nRaw TLC outputs: {OUT_DIR}")
print(f"CSV summary:     {csv_path}")
