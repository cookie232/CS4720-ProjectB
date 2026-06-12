import os
import argparse
from pathlib import Path
from subprocess import Popen

_tools_dir = Path(__file__).parent.parent / "tools"
tla_cp = os.pathsep.join([
    str(_tools_dir / "tla2tools.jar"),
    str(_tools_dir / "CommunityModules-deps.jar"),
])
# Run TLC
def run_tla(trace_spec,trace="trace.ndjson",config="conf.ndjson",dfs=False):
    os.environ["TRACE_PATH"] = trace
    os.environ["CONFIG_PATH"] = config
    if dfs:
        tla_trace_validation_process = Popen([
            "java",
            "-XX:+UseParallelGC",
            "-Dtlc2.tool.queue.IStateQueue=StateDeque",
            "-cp",
            tla_cp,
            "tlc2.TLC",
            trace_spec])
    else:
        tla_trace_validation_process = Popen([
            "java",
            "-XX:+UseParallelGC",
            "-Dtlc2.tool.impl.Tool.cdot=true",
            "-cp",
            tla_cp,
            "tlc2.TLC",
            "-dump",
            "dot,snapshot,colorize,actionlabel,constrained",
            "TD.dot",
            trace_spec])
    tla_trace_validation_process.wait()
    tla_trace_validation_process.terminate()

if __name__ == "__main__":
    # Read program args
    parser = argparse.ArgumentParser(description="")
    parser.add_argument('spec', type=str, help="Specification file")
    parser.add_argument('--trace', type=str, required=False, default="trace.ndjson", help="Trace file")
    parser.add_argument('--config', type=str, required=False, default="conf.ndjson", help="Config file")
    # parser.add_argument('-dfs', '--dfs', type=bool, action=argparse.BooleanOptionalAction, help="breadth-first search")
    parser.add_argument('-dfs', '--dfs', default=False, action=argparse.BooleanOptionalAction, help="breadth-first search")
    args = parser.parse_args()
    # Run
    run_tla(args.spec,args.trace,args.config,args.dfs)

