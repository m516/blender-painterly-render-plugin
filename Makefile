BUILD_DIR ?= build/dev
# The project virtual environment (Python 3.13, `make env`). Override it when the environment lives elsewhere,
# as it does in the offline worker clones: VENV=/path/to/.venv.
VENV ?= .venv
BLENDER_VERSION ?= 5.2.2
# Absolute, so that the tests and painterly_analysis resolve it against this checkout even when they are imported
# from a shared environment elsewhere (a worker clone borrows MAIN/.venv). With the defaults this is the same path
# the relative value already resolved to, because both readers resolve a relative value against the repo root.
export PAINTERLY_BUILD_DIR = $(abspath $(BUILD_DIR))
export PATH := $(abspath $(VENV)/bin):$(PATH)
# Where `make blender` installs the executable. Nothing touches the network at parse time.
BLENDER ?= $(abspath .cache/blender/blender-$(BLENDER_VERSION)-linux-x64/blender)
export BLENDER
# Extra CMake options appended to the configure commands of `build` and `oracle`. The offline worker clones use it to
# point FetchContent at the prepared dependency sources, e.g.
# CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=... -DFETCHCONTENT_SOURCE_DIR_DOCTEST=...".
# Empty by default, so CI configures exactly as before.
CMAKE_ARGS ?=

# The configure command of `build` and `oracle`. $(1) is the build directory; the CMake options follow.
PAINTERLY_CONFIGURE = cmake -S . -B $(1) -G Ninja -DCMAKE_BUILD_TYPE=Release -DPython_EXECUTABLE=$(abspath $(VENV)/bin/python)

# A prepared dependency source tree can be read-only, as MAIN/.cache/src/ is. Embree's CMakeLists.txt writes generated
# headers (kernels/config.h, kernels/hash.h, include/embree4/rtcore_config.h and the export maps) into its own source
# tree, so CMake cannot configure from a read-only copy. For every read-only -DFETCHCONTENT_SOURCE_DIR_<name> in
# $(CMAKE_ARGS), copy the tree into $(1)/_deps-src/<name> once and configure from the copy. The default ($(CMAKE_ARGS)
# empty) takes the other branch and runs no staging at all, so the command line is unchanged.
define PAINTERLY_STAGE_READONLY_SOURCES
set -e; set --; for a in $(CMAKE_ARGS); do case "$$a" in -DFETCHCONTENT_SOURCE_DIR_*=*) n=$${a#-DFETCHCONTENT_SOURCE_DIR_}; n=$${n%%=*}; d=$${a#*=}; if [ -d "$$d" ] && [ ! -w "$$d" ]; then s="$(1)/_deps-src/$$n"; if [ ! -e "$$s" ]; then mkdir -p "$$(dirname "$$s")"; cp -a "$$d" "$$s"; chmod -R u+w "$$s"; fi; a="-DFETCHCONTENT_SOURCE_DIR_$$n=$$s"; fi;; esac; set -- "$$@" "$$a"; done
endef

.PHONY: env env-blender blender build oracle wheel test-cpp test-py test test-slow lint format audit vendor-check check clean

env:
	uv sync --locked --group dev --group analysis

env-blender:
	uv sync --locked --group dev --group analysis --group blender

# Fetches and verifies Blender BLENDER_VERSION (5.2.2 by default) under .cache/blender/ and prints the executable's path.
# A second run only verifies.
blender:
	$(VENV)/bin/python tools/fetch_blender.py --version $(BLENDER_VERSION)

build:
	$(if $(strip $(CMAKE_ARGS)),$(call PAINTERLY_STAGE_READONLY_SOURCES,$(BUILD_DIR)); $(call PAINTERLY_CONFIGURE,$(BUILD_DIR)) "$$@",$(call PAINTERLY_CONFIGURE,$(BUILD_DIR)) $(CMAKE_ARGS))
	cmake --build $(BUILD_DIR)

# The experiments' oracle, built alone into .cache/oracle-build. `make clean` does not touch it, so the renders
# in .cache/renders stay valid. Run experiments with PAINTERLY_BUILD_DIR=.cache/oracle-build.
ORACLE_BUILD_DIR ?= .cache/oracle-build
oracle:
	$(if $(strip $(CMAKE_ARGS)),$(call PAINTERLY_STAGE_READONLY_SOURCES,$(ORACLE_BUILD_DIR)); $(call PAINTERLY_CONFIGURE,$(ORACLE_BUILD_DIR)) -DPAINTERLY_BUILD_MODULE=OFF -DPAINTERLY_BUILD_TESTS=OFF "$$@",$(call PAINTERLY_CONFIGURE,$(ORACLE_BUILD_DIR)) -DPAINTERLY_BUILD_MODULE=OFF -DPAINTERLY_BUILD_TESTS=OFF $(CMAKE_ARGS))
	cmake --build $(ORACLE_BUILD_DIR) --target smallpaint_oracle

# The stable-ABI wheel (cp312-abi3) in dist/. scikit-build-core builds it in build/<wheel tag>, apart from build/dev.
wheel:
	uv build --wheel --out-dir dist/

test-cpp: build
	ctest --test-dir $(BUILD_DIR) --output-on-failure

test-py: build
	$(VENV)/bin/python -m pytest -m "not slow" -q

test: test-cpp test-py

test-slow: build
	$(VENV)/bin/python -m pytest -q

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	git ls-files --cached --others --exclude-standard 'src/*.cpp' 'src/*.h' | xargs -r $(VENV)/bin/clang-format --dry-run --Werror

format:
	$(VENV)/bin/ruff format .
	git ls-files --cached --others --exclude-standard 'src/*.cpp' 'src/*.h' | xargs -r $(VENV)/bin/clang-format -i

audit: build
	@test -n "$(firstword $(wildcard $(BUILD_DIR)/src/blender/_painterly*.so))" || { echo "audit: no _painterly*.so under $(BUILD_DIR)/src/blender" >&2; exit 1; }
	$(VENV)/bin/python tools/symbol_audit.py $(firstword $(wildcard $(BUILD_DIR)/src/blender/_painterly*.so))

# The symbol audit and the vendor check run once each, inside test-py (tests/core/test_symbol_audit.py and
# tests/core/test_vendored.py, which CI's `make test` also runs). `make audit` and `make vendor-check` run them
# alone (TQ.1 F15).
check: lint build test

# Offline check that third_party/cycles matches VENDORED.toml (T3.1); no network access.
vendor-check:
	$(VENV)/bin/python tools/vendor_sync.py check

clean:
	rm -rf build
