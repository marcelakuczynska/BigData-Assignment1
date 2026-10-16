import sys
import time


def multiply(a, b):
    n = len(a)
    c = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            for k in range(n):
                c[i][j] += a[i][k] * b[k][j]
    return c


def main():
    input_path, output_path, warmups_s, repeats_s = sys.argv[1:5]
    warmups, repeats = int(warmups_s), int(repeats_s)
    with open(input_path, encoding="ascii") as f:
        tokens = [int(t) for t in f.read().split()]
    n = tokens[0]
    assert len(tokens) == 1 + 2 * n * n, "Invalid input size"
    data = tokens[1:]
    a = [data[i * n:(i + 1) * n] for i in range(n)]
    offset = n * n
    b = [data[offset + i * n:offset + (i + 1) * n] for i in range(n)]

    for _ in range(warmups):
        result = multiply(a, b)
        assert len(result) == n

    result = None
    for rep in range(1, repeats + 1):
        start = time.perf_counter_ns()
        result = multiply(a, b)
        elapsed = time.perf_counter_ns() - start
        assert len(result) == n
        print(f"MEAS,{rep},{elapsed}", flush=True)

    with open(output_path, "w", encoding="ascii") as f:
        for row in result:
            f.write(" ".join(map(str, row)) + "\n")
    time.sleep(0.15)


if __name__ == "__main__":
    main()
