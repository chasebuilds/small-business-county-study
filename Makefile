PY ?= python

.PHONY: all fetch extract build test
all: ; $(PY) make.py all
fetch: ; $(PY) make.py fetch
extract: ; $(PY) make.py extract
build: ; $(PY) make.py build
test: ; $(PY) make.py test
