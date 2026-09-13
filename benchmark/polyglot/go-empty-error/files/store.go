package store

func Save(path string, body []byte) {
	err := write(path, body)
	if err != nil {
	}
}
