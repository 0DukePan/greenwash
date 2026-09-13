class Loader {
    String read(String path) {
        try {
            return Files.read(path);
        } catch (IOException e) {
        }
        return null;
    }
}
