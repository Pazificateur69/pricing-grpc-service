.PHONY: help install proto run client bench grpcurl test lint typecheck check precommit docker docker-up docker-down clean

PYTHON ?= python3
PROTO_DIR := proto
OUT_DIR := src/pricing_grpc_service/generated
IMAGE := pricing-grpc-service:dev

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

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

run:  ## Run the gRPC server on :50051 (metrics on :9090).
	$(PYTHON) -m pricing_grpc_service

client:  ## Run the example client against localhost:50051.
	$(PYTHON) examples/client.py

bench:  ## Run the latency benchmark against a running server.
	$(PYTHON) bench/bench.py --concurrency 32 --duration 5

grpcurl:  ## List services exposed via reflection (requires grpcurl).
	grpcurl -plaintext localhost:50051 list

test:  ## Run the test suite.
	$(PYTHON) -m pytest -q

lint:  ## Run ruff.
	$(PYTHON) -m ruff check .

typecheck:  ## Run mypy in strict mode.
	$(PYTHON) -m mypy src

check: lint typecheck test  ## Run lint, type-check and tests.

precommit:  ## Run pre-commit on all files.
	pre-commit run --all-files

docker:  ## Build the runtime container image.
	docker build -t $(IMAGE) .

docker-up:  ## Start service + Prometheus via docker-compose.
	docker compose up --build -d

docker-down:  ## Stop the docker-compose stack.
	docker compose down -v

clean:  ## Remove caches and build artifacts.
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
