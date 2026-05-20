.PHONY: help install proto run client test lint typecheck check clean

PYTHON ?= python3
PROTO_DIR := proto
OUT_DIR := src/pricing_grpc_service/generated

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Create a venv and install the package with dev extras.
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e ".[dev]"

proto:  ## Regenerate gRPC stubs from .proto files.
	$(PYTHON) -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(OUT_DIR) \
		--grpc_python_out=$(OUT_DIR) \
		--pyi_out=$(OUT_DIR) \
		$(PROTO_DIR)/pricing.proto
	@# Rewrite the absolute import emitted by protoc into a package-relative one.
	@sed -i.bak 's/^import pricing_pb2/from . import pricing_pb2/' $(OUT_DIR)/pricing_pb2_grpc.py
	@rm -f $(OUT_DIR)/pricing_pb2_grpc.py.bak

run:  ## Run the gRPC server on :50051.
	$(PYTHON) -m pricing_grpc_service

client:  ## Run the example client against localhost:50051.
	$(PYTHON) examples/client.py

test:  ## Run the test suite.
	$(PYTHON) -m pytest -q

lint:  ## Run ruff.
	$(PYTHON) -m ruff check .

typecheck:  ## Run mypy in strict mode.
	$(PYTHON) -m mypy src

check: lint typecheck test  ## Run lint, type-check and tests.

clean:  ## Remove caches and build artifacts.
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
