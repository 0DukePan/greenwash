package calc

func Add(a, b int) int {
	return a + b
}

func Save(path string) error {
	return write(path)
}
