CACHE_DIR := .tectonic-cache
export TECTONIC_CACHE_DIR := $(abspath $(CACHE_DIR))

pdf:
	tectonic -X compile src/main.tex --outdir build

clean:
	rm -rf build/*

purge-cache:
	rm -rf $(CACHE_DIR)

.PHONY: pdf clean purge-cache
