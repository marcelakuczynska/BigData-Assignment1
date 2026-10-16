#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
#endif

static int64_t *multiply(const int64_t *a, const int64_t *b, int n) {
    size_t elements = (size_t)n * (size_t)n;
    int64_t *c = (int64_t *)calloc(elements, sizeof(int64_t));
    if (!c) { fprintf(stderr, "Out of memory\n"); exit(2); }
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            for (int k = 0; k < n; ++k) {
                c[(size_t)i*n + j] += a[(size_t)i*n + k] * b[(size_t)k*n + j];
            }
        }
    }
    return c;
}

static int64_t monotonic_ns(void) {
#ifdef _WIN32
    LARGE_INTEGER frequency, counter;
    QueryPerformanceFrequency(&frequency);
    QueryPerformanceCounter(&counter);
    return (int64_t)((long double)counter.QuadPart * 1000000000.0L / frequency.QuadPart);
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (int64_t)ts.tv_sec * 1000000000LL + ts.tv_nsec;
#endif
}

int main(int argc, char **argv) {
    if (argc != 5) { fprintf(stderr, "Usage: input output warmups repeats\n"); return 1; }
    int warmups = atoi(argv[3]), repeats = atoi(argv[4]);
    FILE *f = fopen(argv[1], "r");
    if (!f) { perror("Opening input"); return 1; }
    int n;
    if (fscanf(f, "%d", &n) != 1 || n < 1 || n > 10000) { fprintf(stderr, "Bad n\n"); return 1; }
    size_t elems = (size_t)n * (size_t)n;
    int64_t *a = (int64_t *)malloc(elems * sizeof(int64_t));
    int64_t *b = (int64_t *)malloc(elems * sizeof(int64_t));
    if (!a || !b) { fprintf(stderr, "Out of memory\n"); return 2; }
    long long temp;
    for (size_t i = 0; i < elems; ++i) {
        if (fscanf(f, "%lld", &temp) != 1) { fprintf(stderr, "Incomplete A\n"); return 1; }
        a[i] = (int64_t)temp;
    }
    for (size_t i = 0; i < elems; ++i) {
        if (fscanf(f, "%lld", &temp) != 1) { fprintf(stderr, "Incomplete B\n"); return 1; }
        b[i] = (int64_t)temp;
    }
    fclose(f);

    int64_t *result = NULL;
    for (int w = 0; w < warmups; ++w) {
        result = multiply(a, b, n);
        if (!result) return 2;
        free(result);
    }
    for (int rep = 1; rep <= repeats; ++rep) {
        int64_t t0 = monotonic_ns();
        result = multiply(a, b, n);
        int64_t elapsed = monotonic_ns() - t0;
        printf("MEAS,%d,%" PRId64 "\n", rep, elapsed);
        fflush(stdout);
        if (rep != repeats) { free(result); result = NULL; }
    }
    f = fopen(argv[2], "w");
    if (!f) { perror("Opening output"); return 1; }
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            if (j) fputc(' ', f);
            fprintf(f, "%" PRId64, result[(size_t)i*n+j]);
        }
        fputc('\n', f);
    }
    fclose(f);
#ifdef _WIN32
    Sleep(150);
#else
    struct timespec pause_time = {0, 150000000L};
    nanosleep(&pause_time, NULL);
#endif
    free(result); free(a); free(b);
    return 0;
}
