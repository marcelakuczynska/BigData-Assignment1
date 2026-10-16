import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parent
SEED = 20261016
DEFAULT_SIZES = [20, 40, 80, 120, 160, 200]
FIELDS = ["language", "n", "repetition", "time_ms", "peak_process_rss_mib",
          "rss_sample_count", "warmups", "seed", "value_range", "numeric_type",
          "compiler_flags", "memory_metric", "correctness"]
MEMORY_METRIC = "max externally sampled process RSS (whole process), 2 ms polling; MiB"


def discover_java():
    suffix = ".exe" if os.name == "nt" else ""
    candidates = []
    if os.environ.get("JAVA_HOME"):
        candidates.append(Path(os.environ["JAVA_HOME"]))
    candidates += [Path.home() / ".jdks" / "openjdk-21"]
    for base in candidates:
        javac, java = base / "bin" / ("javac" + suffix), base / "bin" / ("java" + suffix)
        if javac.is_file() and java.is_file():
            return str(javac), str(java)
    java, javac = shutil.which("java"), shutil.which("javac")
    if java and javac:
        return javac, java
    raise RuntimeError("Java JDK not found. On your machine check ~/.jdks/openjdk-21.")


def discover_gcc():
    if os.name == "nt":
        gcc = Path("C:/msys64/ucrt64/bin/gcc.exe")
        if gcc.is_file():
            os.environ["PATH"] = str(gcc.parent) + os.pathsep + os.environ.get("PATH", "")
            return str(gcc)
    gcc = shutil.which("gcc")
    if gcc: return gcc
    raise RuntimeError("GCC not found (expected C:/msys64/ucrt64/bin/gcc.exe).")


def command_version(argv):
    cp = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, timeout=15)
    if cp.returncode != 0: raise RuntimeError(f"Version check failed: {argv}: {cp.stderr}")
    return (cp.stdout or cp.stderr).splitlines()[0].strip()


def compile_programs():
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    gcc = discover_gcc()
    javac, java = discover_java()
    c_executable = build / ("matrix_c.exe" if os.name == "nt" else "matrix_c")
    cmds = [
        [gcc, "-std=c11", "-O0", "-Wall", "-Wextra", str(ROOT / "matrix_c.c"), "-o", str(c_executable)],
        [javac, "-d", str(build), str(ROOT / "MatrixJava.java")],
    ]
    for cmd in cmds:
        print("BUILD:", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=ROOT, check=True)
    info = {
        "compiler_c": command_version([gcc, "--version"]),
        "compiler_java": command_version([javac, "-version"]),
        "runtime_java": command_version([java, "-version"]),
        "flags_c": "-std=c11 -O0 -Wall -Wextra",
        "flags_java": "javac default settings; JVM JIT enabled; 2 warmups by default",
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "gcc_path": gcc, "javac_path": str(javac).replace(str(Path.home()), "<HOME>"),
    }
    return {
        "Python": [sys.executable, str(ROOT / "matrix_python.py")],
        "Java": [java, "-cp", str(build), "MatrixJava"],
        "C": [str(c_executable)],
    }, info


def save_matrices(path, a, b):
    n = len(a)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as f:
        f.write(str(n) + "\n")
        for matrix in [a, b]:
            for row in matrix:
                f.write(" ".join(map(str, row)) + "\n")


def generate_matrices(n):
    rng = random.Random(SEED + n)
    a = [[rng.randrange(10) for _ in range(n)] for _ in range(n)]
    b = [[rng.randrange(10) for _ in range(n)] for _ in range(n)]
    return a, b


def reference_multiply(a, b):
    n = len(a)
    return [[sum(a[i][k] * b[k][j] for k in range(n))
             for j in range(n)] for i in range(n)]


def validate_output(path, expected):
    with path.open(encoding="ascii") as f:
        actual = [[int(v) for v in line.split()] for line in f if line.strip()]
    if actual != expected:
        raise AssertionError(f"Wrong matrix product in {path}; expected size {len(expected)}")


def run_worker(cmd, input_file, output_file, warmups, repeats, timeout_s, memory_mib):
    full_command = cmd + [str(input_file), str(output_file), str(warmups), str(repeats)]
    process = subprocess.Popen(full_command, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
    observed_rss = 0
    sample_count = 0
    handle = psutil.Process(process.pid)
    began = time.monotonic()
    reason = None
    while process.poll() is None:
        try:
            rss = handle.memory_info().rss
            observed_rss = max(observed_rss, rss)
            sample_count += 1
            if rss > memory_mib * 1024 * 1024:
                reason = "memory_limit"
                process.kill()
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        if time.monotonic() - began > timeout_s:
            reason = "timeout"
            process.kill()
            break
        time.sleep(0.002)
    out, err = process.communicate(timeout=20)
    if reason:
        return None, observed_rss, sample_count, reason, err
    if process.returncode != 0:
        return None, observed_rss, sample_count, "error", err + "\n" + out
    samples = []
    for line in out.splitlines():
        if line.startswith("MEAS,"):
            _, rep, ns = line.split(",")
            samples.append((int(rep), int(ns)))
    if len(samples) != repeats or [r for r, _ in samples] != list(range(1, repeats + 1)):
        return None, observed_rss, sample_count, "invalid_measurements", out + "\n" + err
    if sample_count == 0:
        return None, observed_rss, sample_count, "no_memory_samples", "Process too short to sample RSS"
    return samples, observed_rss, sample_count, "ok", ""


def write_csv(path, rows, headers):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def get_iqr(values):
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    return quartiles[2] - quartiles[0]


def collect_environment(compile_info, args):
    cpu_model = platform.processor() or "Not detected; supply CPU model manually"
    if sys.platform == "win32":
        try:
            cp = subprocess.run(["powershell", "-NoProfile", "-Command",
                                 "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"],
                                capture_output=True, text=True, timeout=15)
            if cp.returncode == 0 and cp.stdout.strip(): cpu_model = cp.stdout.strip()
        except (OSError, subprocess.TimeoutExpired): pass
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "host_os": platform.platform(), "cpu_model": cpu_model,
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_processors": psutil.cpu_count(logical=True),
        "ram_total_gib": round(psutil.virtual_memory().total / (1024**3), 2),
        "versions": compile_info,
        "psutil_version": psutil.__version__,
        "numeric_type": "signed integer (C/Java int64; Python arbitrary precision)",
        "input_storage": "n then n*n entries A and n*n entries B, whitespace-separated ASCII integers",
        "random_generator": "Python random.Random (Mersenne Twister)",
        "seed_formula": "20261016 + n", "value_range": "integers 0..9 inclusive",
        "algorithm": "i-j-k triple loop, O(n^3); allocation/zero-init included in kernel time",
        "matrix_layout": {
            "Python": "list of lists of references to Python int objects",
            "Java": "long[][], array of row-array references; long primitive entries",
            "C": "contiguous, row-major int64_t arrays",
        },
        "measurement_boundary_time": "ONLY single multiplication call, including C output allocation/zero-init; input reading/output writing excluded",
        "measurement_boundary_memory": MEMORY_METRIC + "; sampled over entire process, including input loading, runtime/JVM and output writing",
        "memory_sampling_interval_ms": 2,
        "memory_sampling_pause_ms": 150,
        "python_timer": "time.perf_counter_ns", "java_timer": "System.nanoTime",
        "c_timer": "QueryPerformanceCounter (Windows) or CLOCK_MONOTONIC (POSIX)",
        "warmups": args.warmups, "measured_repetitions": args.repeats,
        "sizes": args.sizes, "timeout_per_process_s": args.timeout,
        "memory_limit_mib_per_process": args.memory_mib,
        "notes": "Uncontrolled background load, Python object representation and JVM baseline overhead limit interpretation.\n"
                 "Warmups excluded from samples. RSS samples may miss short-lived peaks and cannot be equated with array bytes."
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=DEFAULT_SIZES)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=90.0, help="per complete worker process")
    parser.add_argument("--memory-mib", type=float, default=1024.0)
    parser.add_argument("--quick", action="store_true", help="exploratory smoke test ONLY, not full evidence")
    args = parser.parse_args()
    if args.quick:
        args.sizes, args.warmups, args.repeats = [10, 20], 1, 2
    if any(n < 2 for n in args.sizes) or args.repeats < 1 or args.warmups < 0:
        parser.error("sizes must be >=2, repeats >=1, warmups >=0")

    commands, compile_info = compile_programs()
    for directory in ["inputs", "outputs", "results", "figures"]:
        (ROOT / directory).mkdir(exist_ok=True)
    environment = collect_environment(compile_info, args)
    (ROOT / "results" / "environment.json").write_text(
        json.dumps(environment, indent=2, ensure_ascii=False), encoding="utf-8")

    cases = []
    a = [[1, 2], [3, 4]]
    b = [[5, 6], [7, 8]]
    cases.append(("known_2x2", a, b))
    cases.append(("identity_2x2", a, [[1, 0], [0, 1]]))
    cases.append(("zero_2x2", a, [[0, 0], [0, 0]]))
    print("\nCORRECTNESS: known 2x2, identity and zero matrices", flush=True)
    for name, a, b in cases:
        input_file = ROOT / "inputs" / (name + ".txt")
        save_matrices(input_file, a, b)
        expected = reference_multiply(a, b)
        for language, cmd in commands.items():
            result_file = ROOT / "outputs" / (name + "_" + language + ".txt")
            meas, rss, count, status, err = run_worker(cmd, input_file, result_file, 0, 1,
                                                       args.timeout, args.memory_mib)
            if status != "ok": raise RuntimeError(f"Self-test failed for {language}: {status}: {err}")
            validate_output(result_file, expected)
            print(f"  PASS {name:<15} {language}", flush=True)

    rows, failures = [], []
    print("\nBENCHMARK: same matrices, 3 languages, i-j-k loops", flush=True)
    for n in args.sizes:
        a, b = generate_matrices(n)
        expected = reference_multiply(a, b)
        input_file = ROOT / "inputs" / f"n_{n}.txt"
        save_matrices(input_file, a, b)
        for language, cmd in commands.items():
            result_file = ROOT / "outputs" / f"{language}_{n}.txt"
            samples, rss, count, status, err = run_worker(
                cmd, input_file, result_file, args.warmups, args.repeats,
                args.timeout, args.memory_mib)
            if status != "ok":
                print(f"  FAIL {language:<7} n={n:<4} {status}: {err[:200]}", flush=True)
                failures.append({"language": language, "n": n, "status": status,
                                 "timeout_s": args.timeout, "memory_limit_mib": args.memory_mib,
                                 "details": err[:600]})
                continue
            validate_output(result_file, expected)
            values = [ns / 1e6 for _, ns in samples]
            for rep, ns in samples:
                rows.append({"language": language, "n": n, "repetition": rep,
                             "time_ms": f"{ns / 1e6:.9f}",
                             "peak_process_rss_mib": f"{rss / (1024**2):.4f}",
                             "rss_sample_count": count,
                             "warmups": args.warmups, "seed": SEED + n,
                             "value_range": "0..9", "numeric_type": "integer",
                             "compiler_flags": compile_info["flags_c"] if language == "C" else
                             compile_info["flags_java"] if language == "Java" else "CPython interpreter",
                             "memory_metric": MEMORY_METRIC, "correctness": "exact_match"})
            print(f"  PASS {language:<7} n={n:<4} median={statistics.median(values):.5f} ms "
                  f"IQR={get_iqr(values):.5f} ms RSS={rss / (1024**2):.2f} MiB", flush=True)
        write_csv(ROOT / "results" / "raw_measurements.csv", rows, FIELDS)
        write_csv(ROOT / "results" / "failures.csv", failures,
                  ["language", "n", "status", "timeout_s", "memory_limit_mib", "details"])

    summary = []
    for n in args.sizes:
        for language in commands:
            relevant = [r for r in rows if r["n"] == n and r["language"] == language]
            if not relevant: continue
            times = [float(r["time_ms"]) for r in relevant]
            summary.append({"language": language, "n": n,
                            "repetitions": len(relevant),
                            "median_time_ms": round(statistics.median(times), 8),
                            "iqr_time_ms": round(get_iqr(times), 8) if len(times) >= 2 else "NA",
                            "peak_process_rss_mib": relevant[0]["peak_process_rss_mib"],
                            "memory_samples": relevant[0]["rss_sample_count"]})
    write_csv(ROOT / "results" / "summary.csv", summary,
              ["language", "n", "repetitions", "median_time_ms", "iqr_time_ms",
               "peak_process_rss_mib", "memory_samples"])
    print("\nSaved results/raw_measurements.csv, summary.csv, failures.csv, environment.json")
    if rows:
        try:
            import plot_results
            plot_results.make_plots(ROOT / "results" / "summary.csv", ROOT / "figures")
            print("Saved figures/time_comparison.png, figures/memory_comparison.png")
        except ImportError:
            print("Plots skipped: install matplotlib with python -m pip install -r requirements.txt")
    print("Done.")


if __name__ == "__main__":
    main()
