BUILD_DIR ?= build/dev
export PAINTERLY_BUILD_DIR = $(BUILD_DIR)
export PATH := $(abspath .venv/bin):$(PATH)

.PHONY: env env-blender build test-cpp test-py test test-slow lint format audit check clean

env:
	uv sync --locked --group dev --group analysis

env-blender:
	uv sync --locked --group dev --group analysis --group blender

build:
	cmake -S . -B $(BUILD_DIR) -G Ninja -DCMAKE_BUILD_TYPE=Release -DPython_EXECUTABLE=$(abspath .venv/bin/python)
	cmake --build $(BUILD_DIR)

test-cpp: build
	ctest --test-dir $(BUILD_DIR) --output-on-failure

test-py: build
	.venv/bin/python -m pytest -m "not slow" -q

test: test-cpp test-py

test-slow: build
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
	git ls-files 'src/*.cpp' 'src/*.h' | xargs -r .venv/bin/clang-format --dry-run --Werror

format:
	.venv/bin/ruff format .
	git ls-files 'src/*.cpp' 'src/*.h' | xargs -r .venv/bin/clang-format -i

audit: build
	.venv/bin/python tools/symbol_audit.py $(BUILD_DIR)/src/blender/_painterly*

check: lint build test audit

clean:
	rm -rf build
