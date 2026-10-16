# Assignment 1 - Matrix Multiplication

This project compares the basic three-loop matrix multiplication algorithm in Python, Java and C. It measures execution time and observed process memory on one machine. The six matrix sizes are 20, 40, 80, 120, 160 and 200.

## Requirements

- Python 3.12 with the packages in `requirements.txt`
- Java JDK 21
- GCC (tested with MSYS2 UCRT64 GCC 16.1 on Windows)

## Run the experiment

Open this folder in VS Code and run:

```bash
python -m pip install -r requirements.txt
python run_experiments.py
```

The script locates Java through `JAVA_HOME`, the default IntelliJ JDK folder `~/.jdks/openjdk-21`, or `PATH`. On Windows it locates GCC at `C:/msys64/ucrt64/bin/gcc.exe` or on `PATH`.

To regenerate the graphs from saved data:

```bash
python plot_results.py
```

## Files

- `matrix_python.py`, `MatrixJava.java`, `matrix_c.c`: the three implementations.
- `run_experiments.py`: input generation, compilation, correctness tests, timing and memory sampling.
- `plot_results.py`: plots the collected summary data.
- `results/raw_measurements.csv`: all 90 timed observations from the Windows laptop.
- `results/summary.csv`: median, IQR and observed maximum RSS for each configuration.
- `results/failures.csv`: recorded failures (none in this run).
- `results/environment.json`: laptop specifications and experiment settings.
- `figures/`: figures generated from these results.
- `report/`: PDF and editable report.

## Experimental settings

The three versions use i-j-k loops and shared input files with values 0-9 and seed `20261016 + n`. The timed section is the multiplication call, including result allocation/initialization. Input loading and output saving are outside the timed section. There are two warm-ups and five measured runs per configuration. Timing is reported with a median and IQR in milliseconds. Memory is the highest externally sampled process RSS in MiB, not the array allocation size; memory sampling covers the full process and can miss brief peaks. The time limit is 90 s and the memory budget is 1024 MiB per process. The C compiler uses `-O0` (no optimization), which is a limitation when interpreting the relative language speeds.

Correctness is checked with small known matrices, identity and zero matrices, and a full output comparison against a separate Python reference. The input and output files are automatically regenerated when running the experiment.

## Disclosure

ChatGPT assisted with planning, code preparation/debugging and report language editing. Measurements are from the student's laptop. The student remains responsible for checking the code and interpreting the results.
