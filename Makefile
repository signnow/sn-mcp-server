HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: up install run fmt test

up:
	pip install -e .
	sn-mcp http --host $(HOST) --port $(PORT)
