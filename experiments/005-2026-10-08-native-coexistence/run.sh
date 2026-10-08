#!/usr/bin/env bash
# Native-coexistence experiment (T2.3). Needs `make build` and `make blender` first.
#
# 1. coexist.py in Blender, plainly and under LD_BIND_NOW=1 LD_DEBUG=bindings (H1, H2).
# 2. The same selftest in the project venv, compared exactly with Blender's (H1).
# 3. bindings.py on the traced run, with coverage of the module's imports (H3).
# 4. The two H3 controls: the module relinked without -u __cxa_pure_virtual (C1), and against the dynamic libstdc++
#    (C2). Each must show at least one violation, so that the instrument is sensitive. C1 is not applicable when
#    Blender's process does not define __cxa_pure_virtual, because its weak import then stays unbound.
#
# Output goes to out/ (git-ignored). Exit status is 0 only when every check passes; the outputs are written either way.
set -uo pipefail

EXP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$EXP_DIR/../.." && pwd)"
BUILD_DIR="${PAINTERLY_BUILD_DIR:-$REPO/build/dev}"
case "$BUILD_DIR" in
  /*) ;;
  *) BUILD_DIR="$REPO/$BUILD_DIR" ;;
esac
VENV_PY="$REPO/.venv/bin/python"
NINJA="$REPO/.venv/bin/ninja"
MODULE="$BUILD_DIR/src/blender/_painterly.abi3.so"
OUT="$EXP_DIR/out"
CTL="$OUT/controls"
STATUS=0

[[ -f "$MODULE" ]] || { echo "run.sh: $MODULE is missing; run make build first" >&2; exit 1; }
BLENDER="${BLENDER:-$("$VENV_PY" "$REPO/tools/fetch_blender.py" --print-path-only)}"
[[ -x "$BLENDER" ]] || { echo "run.sh: no Blender executable; run make blender first" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$CTL"
cd "$EXP_DIR" || exit 1
note() { printf '%s\n' "$*" | tee -a "$OUT/run.log"; }
note "blender: $BLENDER"
note "module:  $MODULE"

# 1. Blender runs. coexist.py writes out/coexist.json each time, so each run is renamed after it finishes.
"$BLENDER" -b --factory-startup --python-exit-code 1 --python coexist.py -- "$BUILD_DIR" \
  > "$OUT/blender_plain.log" 2>&1
code=$?
note "plain run (H2): blender exit $code"
[[ $code -eq 0 ]] || STATUS=1
mv "$OUT/coexist.json" "$OUT/coexist_plain.json" 2> /dev/null || true

# Traced runs bind every import at load (LD_BIND_NOW=1), so the trace shows each undefined symbol once (H3 coverage).
LD_BIND_NOW=1 LD_DEBUG=bindings LD_DEBUG_OUTPUT="$OUT/ld" \
  "$BLENDER" -b --factory-startup --python-exit-code 1 --python coexist.py -- "$BUILD_DIR" \
  > "$OUT/blender_traced.log" 2>&1
code=$?
note "traced run (H2, H3 trace): blender exit $code"
[[ $code -eq 0 ]] || STATUS=1
mv "$OUT/coexist.json" "$OUT/coexist_traced.json" 2> /dev/null || true

# 2. H1: the venv selftest must equal Blender's selftest exactly, and tasking_system must be 0.
"$VENV_PY" -c 'import json, sys; sys.path.insert(0, sys.argv[1]); import _painterly; print(json.dumps(_painterly.selftest(), sort_keys=True))' \
  "$BUILD_DIR/src/blender" > "$OUT/venv_selftest.json"
"$VENV_PY" - "$OUT" <<'PY' | tee -a "$OUT/run.log"
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
venv = json.loads((out / "venv_selftest.json").read_text())
ok = venv.get("tasking_system") == 0
for name in ("coexist_plain.json", "coexist_traced.json"):
    path = out / name
    if not path.exists():
        print(f"H1 {name}: missing (the Blender run did not finish)")
        ok = False
        continue
    blender = json.loads(path.read_text())["selftest"]
    equal = blender == venv
    ok = ok and equal
    print(f"H1 {name}: selftest equal to venv: {equal}; tasking_system: {blender.get('tasking_system')}")
print(f"H1 venv selftest: {venv}")
sys.exit(0 if ok else 1)
PY
[[ ${PIPESTATUS[0]} -eq 0 ]] || STATUS=1

# 3. H3: violations and import coverage of the bindings that the traced run's _painterly makes.
"$VENV_PY" "$EXP_DIR/bindings.py" "$OUT" --module "$MODULE" | tee -a "$OUT/run.log" || STATUS=1
"$VENV_PY" - "$OUT/bindings.json" <<'PY' | tee -a "$OUT/run.log"
import json
import sys

result = json.load(open(sys.argv[1], encoding="utf-8"))
ok = result["coverage_complete"] and result["violation_count"] == 0
print(
    f"H3 (traced run): coverage {result['matched_bindings']}/{result['expected_bindings']} "
    f"(complete: {result['coverage_complete']}); violations: {result['violation_count']}; "
    f"H3 {'supported' if ok else 'refuted'}"
)
sys.exit(0 if ok else 1)
PY
[[ ${PIPESTATUS[0]} -eq 0 ]] || STATUS=1

# 4. H3 controls. The link command comes from ninja. Control C1 drops -Wl,-u,__cxa_pure_virtual. Control C2 drops
#    -static-libstdc++ -static-libgcc. Both also drop --dependency-file, so the build's link.d is left untouched.
LINK_CMD="$("$NINJA" -C "$BUILD_DIR" -t commands src/blender/_painterly.abi3.so | tail -n 1)"
relink() {  # $1: name, $2: sed expression that removes the flag under test
  local dir="$CTL/$1"
  mkdir -p "$dir"
  printf '%s\n' "$LINK_CMD" \
    | sed -e "$2" \
      -e 's# -Wl,--dependency-file=[^ ]*##' \
      -e "s#-o src/blender/_painterly.abi3.so#-o $dir/_painterly.abi3.so#" \
    > "$dir/relink.sh"
  (cd "$BUILD_DIR" && bash "$dir/relink.sh") > "$dir/relink.log" 2>&1
  note "control $1: relink exit $?"
}
relink no_cxa 's# -Wl,-u,__cxa_pure_virtual##'
relink dyn_libstdc 's# -static-libstdc++ -static-libgcc##'

# C1 applies only if the process that loads the module defines __cxa_pure_virtual: the Blender executable, or a
# library that ldd lists for it. Otherwise the weak import stays unbound and no trace can show it.
process_defines() {  # $1: symbol; true when one of those objects defines it in its dynamic symbol table
  local obj
  while IFS= read -r obj; do
    nm -D --defined-only "$obj" 2> /dev/null \
      | awk -v s="$1" '{ name = $NF; sub(/@.*/, "", name); if (name == s) found = 1 } END { exit !found }' \
      && return 0
  done < <({ printf '%s\n' "$BLENDER"; ldd "$BLENDER" | awk '$2 == "=>" && $3 ~ /^\// { print $3 }'; })
  return 1
}
c1_applicable=no
process_defines __cxa_pure_virtual && c1_applicable=yes
note "C1 applicable (Blender's process defines __cxa_pure_virtual): $c1_applicable"

# The control runs load the module and call selftest(), so that the lazily bound calls are traced too. A control run
# that crashes is recorded, and its trace is still counted.
for name in no_cxa dyn_libstdc; do
  dir="$CTL/$name"
  if [[ $name == no_cxa && $c1_applicable == no ]]; then
    note "control $name: not applicable (Blender's process does not define __cxa_pure_virtual)"
    continue
  fi
  LD_BIND_NOW=1 LD_DEBUG=bindings LD_DEBUG_OUTPUT="$dir/ld" "$BLENDER" -b --factory-startup \
    --python-expr "import sys; sys.path.insert(0, '$dir'); import _painterly; _painterly.selftest()" \
    > "$dir/blender.log" 2>&1
  note "control $name: blender exit $?"
  "$VENV_PY" "$EXP_DIR/bindings.py" "$dir" --module "$dir/_painterly.abi3.so" > "$dir/bindings.log" 2>&1
  violations="$(cat "$dir/bindings_summary.txt" 2> /dev/null || echo missing)"
  note "control $name: violations $violations; $(cat "$dir/bindings.log" 2> /dev/null || echo 'no bindings.py output')"
  [[ "$violations" =~ ^[0-9]+$ && "$violations" -ge 1 ]] || { note "control $name: insensitive instrument"; STATUS=1; }
done

if [[ $STATUS -eq 0 ]]; then
  note "run.sh: all checks passed"
else
  note "run.sh: at least one check failed; see out/run.log and out/*.json"
fi
exit $STATUS
