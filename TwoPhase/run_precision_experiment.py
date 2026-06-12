"""
Run TLC on each trace-precision configuration (VEA, V, VpEA, EA, E)
for 4/8/12/16 RMs, under both BFS and DFS, and collect metrics.
Matches the experiment reported in Fig. 5 of the paper.
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
OUT_DIR   = BASE / "results" / "precision"
TLA_CP    = (
    str(BASE.parent / "tools" / "tla2tools.jar") + ";" +
    str(BASE.parent / "tools" / "CommunityModules-deps.jar")
)

RM_COUNTS = [4, 8, 12, 16]
CFGS      = ["VEA", "V", "VpEA", "EA", "E"]

# Paper's Fig. 5 reference values: (BFS distinct, DFS distinct); None = ∞ (timeout)
PAPER_REF = {
    (4,  "VEA"): (19,       19),
    (4,  "V"):   (211,      35),
    (4,  "VpEA"):(19,       19),
    (4,  "EA"):  (48,       22),
    (4,  "E"):   (246,      58),
    (8,  "VEA"): (35,       35),
    (8,  "V"):   (8_000,    73),
    (8,  "VpEA"):(35,       35),
    (8,  "EA"):  (640,      42),
    (8,  "E"):   (22_000,   695),
    (12, "VEA"): (74,       74),
    (12, "V"):   (None,     209),
    (12, "VpEA"):(74,       74),
    (12, "EA"):  (11_000,   86),
    (12, "E"):   (2_500_000,27_000),
    (16, "VEA"): (91,       91),
    (16, "V"):   (None,     270),
    (16, "VpEA"):(91,       91),
    (16, "EA"):  (205_000,  107),
    (16, "E"):   (None,     557_000),
}

BFS_TIMEOUT = 300   # 5 min; paper used 1 hr, we note timeout as ∞
DFS_TIMEOUT = 120   # 2 min; DFS should always finish well within this


def build_cmd(dfs: bool) -> list:
    cmd = ["java", "-XX:+UseParallelGC"]
    if dfs:
        cmd.append("-Dtlc2.tool.queue.IStateQueue=StateDeque")
    cmd += ["-cp", TLA_CP, "tlc2.TLC", "-note", SPEC]
    return cmd


def run_tlc(trace: Path, conf: Path, dfs: bool) -> tuple:
    """Returns (output_text, elapsed_seconds, timed_out)."""
    env = os.environ.copy()
    env["TRACE_PATH"] = str(trace)
    env["CONFIG_PATH"] = str(conf)
    timeout = DFS_TIMEOUT if dfs else BFS_TIMEOUT
    t0 = time.time()
    try:
        proc = subprocess.run(
            build_cmd(dfs), env=env, cwd=str(BASE),
            capture_output=True, text=True, timeout=timeout,
        )
        return proc.stdout + proc.stderr, time.time() - t0, False
    except subprocess.TimeoutExpired:
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
    m3 = re.search(r"Finished in (\d+)s", output)
    tlc_s = int(m3.group(1)) if m3 else None
    return dict(verdict=verdict, states=states, distinct=distinct, depth=depth, tlc_s=tlc_s)


OUT_DIR.mkdir(parents=True, exist_ok=True)
csv_path = OUT_DIR / "summary.csv"
rows = []

hdr = f"{'Instance':<16} {'Mode':<4} {'Verdict':<8} {'States':>9} {'Distinct':>9} {'Depth':>6} {'Time':>7}  {'Paper':>9}"
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
            ref_b, ref_d = PAPER_REF.get((rm, cfg), (None, None))
            paper_val = ref_d if dfs else ref_b
            paper_str = "∞" if paper_val is None else f"{paper_val:,}"

            print(f"  Running {label} {mode} ...", end="", flush=True)
            output, elapsed, timed_out = run_tlc(trace, conf, dfs)

            raw_file = OUT_DIR / f"{rm}RM-{cfg}-{mode}.txt"
            raw_file.write_text(output)

            if timed_out:
                row = dict(rm=rm, cfg=cfg, mode=mode, verdict="TIMEOUT",
                           states=None, distinct=None, depth=None,
                           elapsed=round(elapsed, 1), paper=paper_str)
                print(f" TIMEOUT ({elapsed:.0f}s)")
            else:
                m = parse(output)
                row = dict(rm=rm, cfg=cfg, mode=mode, verdict=m["verdict"],
                           states=m["states"], distinct=m["distinct"], depth=m["depth"],
                           elapsed=round(elapsed, 1), paper=paper_str)
                dist_s = f"{m['distinct']:,}" if m["distinct"] is not None else "?"
                print(f" {m['verdict']:<7} states={m['states']}, distinct={m['distinct']}, depth={m['depth']}, {elapsed:.1f}s")

            rows.append(row)
            dist_str = f"{row['distinct']:,}" if row["distinct"] else row["verdict"]
            print(f"{'':>2}{label:<16} {mode:<4} {row['verdict']:<8} "
                  f"{str(row['states'] or ''):>9} {dist_str:>9} "
                  f"{str(row['depth'] or ''):>6} {elapsed:>6.1f}s  {paper_str:>9}")

# Write CSV
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["rm","cfg","mode","verdict","states","distinct","depth","elapsed","paper"])
    w.writeheader()
    w.writerows(rows)

# Print compact summary table matching paper's Fig. 5 layout
print("\n" + "=" * 80)
print("SUMMARY — Distinct states (BFS / DFS) vs paper Fig. 5")
print("=" * 80)
print(f"{'Instance':<16}", end="")
for cfg in CFGS:
    print(f"  {cfg:>14}", end="")
print()
print("-" * (16 + 16 * len(CFGS)))

for rm in RM_COUNTS:
    print(f"TP {rm}RM{'':<9}", end="")
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

print("\nPaper reference (BFS/DFS):")
for rm in RM_COUNTS:
    print(f"TP {rm}RM{'':<9}", end="")
    for cfg in CFGS:
        ref_b, ref_d = PAPER_REF.get((rm, cfg), (None, None))
        b = "∞" if ref_b is None else f"{ref_b:,}"
        d = "∞" if ref_d is None else f"{ref_d:,}"
        cell = f"{b}/{d}"
        print(f"  {cell:>14}", end="")
    print()

print(f"\nRaw TLC outputs: {OUT_DIR}")
print(f"CSV summary:     {csv_path}")
