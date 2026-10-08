BUILD_DIR ?= build/dev
BLENDER_VERSION ?= 5.2.2
export PAINTERLY_BUILD_DIR = $(BUILD_DIR)
export PATH := $(abspath .venv/bin):$(PATH)
# Where `make blender` installs the executable. Nothing touches the network at parse time.
BLENDER ?= $(abspath .cache/blender/blender-$(BLENDER_VERSION)-linux-x64/blender)
export BLENDER

.PHONY: env env-blender blender build test-cpp test-py test test-slow lint format audit check clean

env:
	uv sync --locked --group dev --group analysis

env-blender:
	uv sync --locked --group dev --group analysis --group blender

# Fetches and verifies Blender BLENDER_VERSION (5.2.2 by default) under .cache/blender/ and prints the executable's path.
# A second run only verifies.
blender:
	.venv/bin/python tools/fetch_blender.py --version $(BLENDER_VERSION)

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
	@test -n "$(firstword $(wildcard $(BUILD_DIR)/src/blender/_painterly*.so))" || { echo "audit: no _painterly*.so under $(BUILD_DIR)/src/blender" >&2; exit 1; }
	.venv/bin/python tools/symbol_audit.py $(firstword $(wildcard $(BUILD_DIR)/src/blender/_painterly*.so))

check: lint build test audit

clean:
	rm -rf build
