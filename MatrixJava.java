import java.io.*;

public class MatrixJava {
    public static long[][] multiply(long[][] a, long[][] b) {
        int n = a.length;
        long[][] c = new long[n][n];
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    c[i][j] += a[i][k] * b[k][j];
                }
            }
        }
        return c;
    }

    private static class FastIntReader implements Closeable {
        private final BufferedInputStream in;
        FastIntReader(String path) throws IOException { in = new BufferedInputStream(new FileInputStream(path)); }
        long nextLong() throws IOException {
            int c;
            do { c = in.read(); } while (c != -1 && c <= ' ');
            if (c == -1) throw new EOFException("Missing matrix element");
            boolean negative = false;
            if (c == '-') { negative = true; c = in.read(); }
            long number = 0;
            while (c >= '0' && c <= '9') {
                number = number * 10 + c - '0';
                c = in.read();
            }
            return negative ? -number : number;
        }
        @Override public void close() throws IOException { in.close(); }
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 4) throw new IllegalArgumentException("Usage: input output warmups repeats");
        int warmups = Integer.parseInt(args[2]);
        int repeats = Integer.parseInt(args[3]);
        long[][] a, b;
        int n;
        try (FastIntReader reader = new FastIntReader(args[0])) {
            n = (int) reader.nextLong();
            a = new long[n][n];
            b = new long[n][n];
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++) a[i][j] = reader.nextLong();
            for (int i = 0; i < n; i++)
                for (int j = 0; j < n; j++) b[i][j] = reader.nextLong();
        }
        long[][] result = null;
        for (int w = 0; w < warmups; w++) {
            result = multiply(a, b);
            if (result.length != n) throw new AssertionError();
        }
        for (int rep = 1; rep <= repeats; rep++) {
            long t0 = System.nanoTime();
            result = multiply(a, b);
            long elapsed = System.nanoTime() - t0;
            if (result.length != n) throw new AssertionError();
            System.out.println("MEAS," + rep + "," + elapsed);
        }
        try (PrintWriter out = new PrintWriter(new BufferedWriter(new FileWriter(args[1])))) {
            for (int i = 0; i < n; i++) {
                for (int j = 0; j < n; j++) {
                    if (j > 0) out.print(' ');
                    out.print(result[i][j]);
                }
                out.println();
            }
        }
        Thread.sleep(150);
    }
}
