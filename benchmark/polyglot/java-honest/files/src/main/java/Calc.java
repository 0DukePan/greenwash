class Calc {
    static int add(int a, int b) {
        return a + b;
    }

    String read(String path) throws IOException {
        return Files.read(path);
    }
}
