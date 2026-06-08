# CS4720 Project B — TLA+ Trace Validation

Reproduction of **"Validating Traces of Distributed Programs Against TLA+ Specifications"** using the **TwoPhase** (Two-Phase Commit) example. We instrument a distributed Java program, merge its execution traces into a single NDJSON file, and use TLC to verify the trace against a TLA+ specification.

TLA+ tools (`tla2tools.jar` and `CommunityModules-deps.jar`) are already included in `tools/` — no download needed.

---

## Prerequisites

| Tool | Version used |
|------|-------------|
| Java | 25.0.2 |
| Maven | 3.9.16 |
| Python | 3.14.3 |

---

## Setup

Run these commands from the repo root:

```powershell
# 1. Clone the repo
git clone https://github.com/cookie232/CS4720-ProjectB.git
cd CS4720-ProjectB

# 2. Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Build the Java TwoPhase implementation
cd TwoPhase
mvn.cmd package
```

---

## Running

From inside the `TwoPhase/` directory:

```powershell
# Full pipeline: build, run Java, merge traces, validate with TLC (BFS)
python trace_validation_pipeline.py -c

# Same but with DFS
python trace_validation_pipeline.py -c --dfs
```

Expected output ends with:
```
Model checking completed. No error has been found.
```

### Validate a saved trace (skip re-running Java)

```powershell
# BFS
python tla_trace_validation.py spec\TwoPhaseTrace.tla --trace results\trace-run1.ndjson

# DFS
python tla_trace_validation.py spec\TwoPhaseTrace.tla --trace results\trace-run1.ndjson --dfs
```

---

## BFS vs DFS Experiment

We generated three traces once, saved them, then ran BFS and DFS on each — isolating search strategy from Java execution timing.

| Trace | Search | TLC result | States generated | Distinct states | Depth | Runtime |
|-------|--------|------------|----------------:|----------------:|------:|--------:|
| trace-run1 | BFS | No error found | 16 | 14 | 14 | <1s |
| trace-run1 | DFS | No error found | 16 | 14 | 14 | <1s |
| trace-run2 | BFS | No error found | 15 | 14 | 14 | ~1s |
| trace-run2 | DFS | No error found | 15 | 14 | 14 | ~1s |
| trace-run3 | BFS | No error found | 13 | 13 | 13 | ~1s |
| trace-run3 | DFS | No error found | 13 | 13 | 13 | <1s |

BFS and DFS produce identical results in trace validation mode — TLC follows a fixed sequence of events, so search order doesn't matter. State count differences across traces reflect non-determinism in the Java execution.

Saved traces and TLC output are in `TwoPhase/results/`.

---

## Project structure

```
CS4720-ProjectB/
├── tools/                          # TLA+ binaries (included)
│   ├── tla2tools.jar
│   └── CommunityModules-deps.jar
├── requirements.txt                # Python dependencies
│
└── TwoPhase/                       # Main working directory
    ├── spec/                       # TLA+ specifications
    │   ├── TwoPhase.tla            # Two-Phase Commit spec
    │   ├── TwoPhaseTrace.tla       # Trace refinement spec
    │   ├── TraceSpec.tla           # Generic trace validation template
    │   └── TVOperators.tla         # Helper operators
    ├── src/                        # Java implementation (instrumented)
    ├── results/                    # Saved traces and TLC output
    │   ├── trace-run{1,2,3}.ndjson
    │   ├── bfs-run{1,2,3}.txt
    │   └── dfs-run{1,2,3}.txt
    ├── trace_validation_pipeline.py # Main pipeline script
    ├── tla_trace_validation.py     # Calls TLC
    ├── run_impl.py                 # Runs the Java processes
    ├── trace_merger.py             # Merges per-process NDJSON into one trace
    └── conf.ndjson                 # Run configuration
```
