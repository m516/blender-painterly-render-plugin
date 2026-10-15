/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* painterly_render: a scratch driver of the native core (firstlight). It renders the SPEC §9
 * smallpaint reference scene through PainterlyPathTrace and writes the same files as
 * src/app/smallpaint_oracle.cpp, in the same layout, so the two can be compared bit for bit
 * (docs/architecture.md, "Determinism contract").
 *
 * The scene is SmallpaintSceneFixture (src/test/smallpaint_scene_fixture.h). Its public kernel data
 * are overridden from the command line: the image size, every integrator knob and the camera
 * jitter. The fixture's own float32-rounded constants (double(0.1f), double(1e-4f) and the jitter
 * 2 * double(float(1 / 1400))) are therefore never used: every default below is the oracle's double
 * literal (smallpaint_oracle.cpp, struct Options).
 *
 * The CLI is the oracle's, for the options the core implements, with the oracle's defaults. Oracle
 * option values the core does not implement are rejected with exit status 2:
 *   --scene standalone        the fixture is the GUI scene only, and the core has no unnormalized
 *                             (P - c) / r sphere normal (SPEC §9 "Standalone 2016 scene").
 *   --chain omp-restart:T, pixel-major, pixel-major-omp:T
 *                             oracle-only chains (SPEC §3); the core has image, row and lane.
 *   --halton incremental      the core always uses vdc(K) (painterly_vdc, SPEC §2), which is the
 *                             oracle's --halton exact. The oracle's default is incremental; the
 *                             driver's default is exact because it is the only value the core has.
 *                             The two agree bit for bit while every chain's K stays below 2^23
 *                             (SPEC §2). meta.json records image_chain_final_k for that check.
 *   --u2 base3                the core has no base-3 Halton (PainterlyU2Mode: same, independent).
 *
 * Mapping of the oracle's enumerations to the kernel (smallpaint_oracle.cpp:43-46, 124, 284-286):
 *   --ghost all     every sphere SPHERE_GHOST (the oracle tests every sphere with the a = 1
 *                   quadratic).
 *   --ghost lights  spheres whose material emission is positive SPHERE_GHOST, the others
 *                   SPHERE_EXACT (the oracle: `g_ghost == lights && emission > 0`).
 *   --ghost none    every sphere SPHERE_EXACT (the oracle's intersect_exact).
 *                   Planes have no intersection mode.
 *   --u2 same         U2_SAME: the oracle's hal2, a base-2 Halton started at the same K0 and
 *                     advanced in lockstep with hal, so u2 = u1.
 *   --u2 independent  U2_INDEPENDENT: rng_unit(seed, PURPOSE_U2, depth, row, col, pass) in both.
 *   --chain image|row|lane:L   CHAIN_IMAGE | CHAIN_ROW | CHAIN_LANE with lane_length L.
 *   --continue-after-emitter yes|no   continue_after_emitter 1 | 0.
 *   --jitter X      KernelPainterlyCamera::jitter = X. Both are image-plane units for the smallpaint
 *                   camera (SPEC §7), so there is no conversion.
 *   --refr X        the ior of every LOBE_GLASS lobe (the oracle's params["refr_index"]). */

#include "painterly/integrator/buffers.h"
#include "painterly/integrator/path_trace.h"
#include "painterly/util/thread_pool.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <string>
#include <thread>
#include <vector>

#include "smallpaint_scene_fixture.h"

#ifndef FIRSTLIGHT_SOURCE_COMMIT
#  define FIRSTLIGHT_SOURCE_COMMIT "unknown"
#endif

CCL_NAMESPACE_BEGIN

namespace {

/* SPEC §2: vdc has period 2^23 (PAINTERLY_VDC_BITS); the oracle's incremental Halton equals vdc
 * bit for bit below it. */
constexpr uint64_t VDC_PERIOD = uint64_t(1) << PAINTERLY_VDC_BITS;

/* The oracle's options (smallpaint_oracle.cpp, struct Options) that the core implements, with the
 * oracle's defaults, plus the driver's --batch. */
struct Options {
  std::string scene = "gui";
  int size = 400;                         /* smallpaint_oracle.cpp:420 (GUI default) */
  int passes = 50;                        /* smallpaint_oracle.cpp:421 (GUI default) */
  double refr = 1.5;                      /* smallpaint_oracle.cpp:422 (GUI default) */
  uint32_t seed = 0;                      /* smallpaint_oracle.cpp:423 */
  std::string chain_text = "image";       /* smallpaint_oracle.cpp:424 */
  int chain = CHAIN_IMAGE;
  int lane_length_requested = 0;          /* lane:L only */
  std::string halton = "exact";           /* the only value the core implements (see above) */
  std::string ghost = "all";              /* smallpaint_oracle.cpp:428 */
  double alpha = 0.0;                     /* smallpaint_oracle.cpp:429 */
  std::string u2 = "same";                /* smallpaint_oracle.cpp:430 */
  std::string continue_after_emitter = "yes"; /* smallpaint_oracle.cpp:431 */
  double jitter = 1.0 / 700.0;            /* smallpaint_oracle.cpp:432; smallpaint_painterly.cpp:291-292 */
  double diffuse_gain = 0.1;              /* smallpaint_oracle.cpp:433; smallpaint_painterly.cpp:209-211 */
  double emission_gain = 2;               /* smallpaint_oracle.cpp:434; smallpaint_painterly.cpp:200 */
  double ray_epsilon = 1e-4;              /* smallpaint_oracle.cpp:435; smallpaint_painterly.cpp:39 */
  int max_depth = 20;                     /* smallpaint_oracle.cpp:436; smallpaint_painterly.cpp:190 */
  int threads = 1;                        /* set to the hardware concurrency in main, as the oracle */
  int batch = 0;                          /* passes per render_passes call; 0 = all in one call */
  std::string out;
};

const char *const usage_text =
    "usage: painterly_render --out DIR [options]\n"
    "  --scene gui                         reference scene (standalone: not implemented)\n"
    "  --size N                            image side in pixels (default 400)\n"
    "  --passes N                          passes (default 50)\n"
    "  --refr X                            glass IOR, X > 0 (default 1.5)\n"
    "  --seed N                            uint32 seed (default 0)\n"
    "  --chain image|row|lane:L            (default image; omp-restart, pixel-major,\n"
    "                                      pixel-major-omp: not implemented)\n"
    "  --halton exact                      (the core's vdc; incremental: not implemented)\n"
    "  --ghost all|lights|none             (default all)\n"
    "  --alpha X                           (default 0)\n"
    "  --u2 same|independent               (default same; base3: not implemented)\n"
    "  --continue-after-emitter yes|no     (default yes)\n"
    "  --jitter X                          image-plane jitter (default 1/700)\n"
    "  --diffuse-gain X                    diffuse bounce gain (default 0.1)\n"
    "  --emission-gain X                   emission gain (default 2)\n"
    "  --ray-epsilon X                     self-intersection eps, X > 0 (default 1e-4)\n"
    "  --max-depth N                       path depth limit, N >= 1 (default 20)\n"
    "  --threads N                         worker threads (default hardware concurrency)\n"
    "  --batch N                           passes per render_passes call (default all)\n"
    "  --out DIR                           output directory, created if missing (required)\n";

int usage_error(const std::string &message)
{
  std::fprintf(stderr, "painterly_render: %s\n%s", message.c_str(), usage_text);
  return 2;
}

int not_implemented(const std::string &flag, const std::string &value)
{
  std::fprintf(stderr,
               "painterly_render: %s %s is an oracle option value the native core does not "
               "implement\n",
               flag.c_str(),
               value.c_str());
  return 2;
}

/* Decimal unsigned integer in [lo, hi] via strtoull. The first character must be a digit, so
 * strtoull's acceptance of "-1" (which it wraps) and of leading blanks never applies. */
bool parse_uint_arg(const std::string &text,
                    const unsigned long long lo,
                    const unsigned long long hi,
                    unsigned long long &value)
{
  if (text.empty() || text[0] < '0' || text[0] > '9') {
    return false;
  }
  char *end = nullptr;
  errno = 0;
  const unsigned long long v = std::strtoull(text.c_str(), &end, 10);
  if (errno != 0 || *end != '\0' || v < lo || v > hi) {
    return false;
  }
  value = v;
  return true;
}

/* As the oracle's parse_double_arg (smallpaint_oracle.cpp:623-630): strtod, the whole text, finite.
 * strtod is correctly rounded, so a Python repr() of a float round-trips to the same double. */
bool parse_double_arg(const std::string &text, double &value)
{
  if (text.empty()) {
    return false;
  }
  char *end = nullptr;
  const double v = std::strtod(text.c_str(), &end);
  if (*end != '\0' || !std::isfinite(v)) {
    return false;
  }
  value = v;
  return true;
}

/* Writes a NumPy .npy file, format version 1.0, byte for byte as the oracle's write_npy
 * (smallpaint_oracle.cpp:526-548). Data are little-endian (x86-64 and arm64 hosts). */
bool write_npy(const std::filesystem::path &path,
               const std::string &descr,
               const std::vector<size_t> &shape,
               const void *data,
               const size_t bytes)
{
  std::string dims;
  for (size_t k = 0; k < shape.size(); ++k) {
    dims += (k > 0 ? ", " : "") + std::to_string(shape[k]);
  }
  const std::string header = "{'descr': '" + descr + "', 'fortran_order': False, 'shape': (" +
                             dims + "), }";
  /* Layout: magic (6 bytes), version (2), header length (2, little-endian), header, '\n'. NumPy
   * pads the header with spaces so that the total length is a multiple of 64 bytes. */
  const size_t prefix_bytes = 10;
  const size_t alignment = 64;
  const size_t unpadded = header.size() + 1;
  const size_t pad = (alignment - (prefix_bytes + unpadded) % alignment) % alignment;
  const size_t header_len = unpadded + pad;
  const unsigned char head[10] = {0x93,
                                  'N',
                                  'U',
                                  'M',
                                  'P',
                                  'Y',
                                  1,
                                  0,
                                  (unsigned char)(header_len & 0xFF),
                                  (unsigned char)(header_len >> 8)};
  const std::string tail = header + std::string(pad, ' ') + "\n";
  FILE *f = std::fopen(path.string().c_str(), "wb");
  if (!f) {
    return false;
  }
  bool ok = std::fwrite(head, 1, sizeof head, f) == sizeof head;
  ok = (std::fwrite(tail.data(), 1, tail.size(), f) == tail.size()) && ok;
  ok = (std::fwrite(data, 1, bytes, f) == bytes) && ok;
  return (std::fclose(f) == 0) && ok;
}

/* image.ppm (binary P6), as the oracle's write_ppm (smallpaint_oracle.cpp:550-559): byte =
 * min((int)sum / passes, 255) per channel (SPEC §7). */
bool write_ppm(const std::filesystem::path &path,
               const PainterlyRenderBuffers &buffers,
               const int passes)
{
  FILE *f = std::fopen(path.string().c_str(), "wb");
  if (!f) {
    return false;
  }
  std::fprintf(f, "P6\n%d %d\n255\n", buffers.width, buffers.height);
  std::vector<unsigned char> bytes(buffers.combined.size());
  for (size_t k = 0; k < buffers.combined.size(); ++k) {
    bytes[k] = (unsigned char)std::min((int)buffers.combined[k] / passes, 255);
  }
  const bool ok = std::fwrite(bytes.data(), 1, bytes.size(), f) == bytes.size();
  return (std::fclose(f) == 0) && ok;
}

struct RunStats {
  int threads = 0;
  int batch = 0;
  int batch_calls = 0;
  int lane_length = 0;
  double wall_seconds = 0.0;
  double object_id_seconds = 0.0;
  uint64_t total_k = 0;
};

bool write_meta(const std::filesystem::path &path,
                const Options &o,
                const KernelPainterlyData &data,
                const RunStats &s)
{
  FILE *f = std::fopen(path.string().c_str(), "w");
  if (!f) {
    return false;
  }
  const KernelPainterlyIntegrator &p = data.integrator;
  std::fprintf(f, "{\n");
  std::fprintf(f, "  \"driver\": \"painterly_render\",\n");
  std::fprintf(f, "  \"source_commit\": \"%s\",\n", FIRSTLIGHT_SOURCE_COMMIT);
  std::fprintf(f, "  \"scene\": \"%s\",\n", o.scene.c_str());
  std::fprintf(f, "  \"camera\": \"smallpaint\",\n");
  std::fprintf(f, "  \"width\": %d,\n", data.cam.width);
  std::fprintf(f, "  \"height\": %d,\n", data.cam.height);
  std::fprintf(f, "  \"passes\": %d,\n", o.passes);
  std::fprintf(f, "  \"refr\": %.17g,\n", o.refr);
  std::fprintf(f, "  \"seed\": %u,\n", (unsigned int)p.seed);
  std::fprintf(f, "  \"chain\": \"%s\",\n", o.chain_text.c_str());
  std::fprintf(f, "  \"chain_enum\": %d,\n", p.chain);
  if (o.chain == CHAIN_LANE) {
    std::fprintf(f, "  \"lane_length_requested\": %d,\n", o.lane_length_requested);
    std::fprintf(f, "  \"lane_length\": %d,\n", s.lane_length);
  }
  else {
    std::fprintf(f, "  \"lane_length_requested\": null,\n");
    std::fprintf(f, "  \"lane_length\": null,\n");
  }
  std::fprintf(f, "  \"halton\": \"%s\",\n", o.halton.c_str());
  std::fprintf(f, "  \"ghost\": \"%s\",\n", o.ghost.c_str());
  std::fprintf(f, "  \"alpha\": %.17g,\n", p.alpha);
  std::fprintf(f, "  \"u2\": \"%s\",\n", o.u2.c_str());
  std::fprintf(f, "  \"u2_mode_enum\": %d,\n", p.u2_mode);
  std::fprintf(f, "  \"continue_after_emitter\": \"%s\",\n", o.continue_after_emitter.c_str());
  std::fprintf(f, "  \"jitter\": %.17g,\n", data.cam.jitter);
  std::fprintf(f, "  \"diffuse_gain\": %.17g,\n", p.diffuse_gain);
  std::fprintf(f, "  \"emission_gain\": %.17g,\n", p.emission_gain);
  std::fprintf(f, "  \"ray_epsilon\": %.17g,\n", p.ray_epsilon);
  std::fprintf(f, "  \"max_depth\": %d,\n", p.max_depth);
  std::fprintf(f, "  \"k0_phase_lock_bits\": %d,\n", p.k0_phase_lock_bits);
  std::fprintf(f, "  \"two_sided\": %d,\n", p.two_sided);
  std::fprintf(f, "  \"spiral_frame\": [");
  for (int i = 0; i < 9; i++) {
    std::fprintf(f, "%s%.17g", i > 0 ? ", " : "", p.spiral_frame[i]);
  }
  std::fprintf(f, "],\n");
  std::fprintf(f, "  \"threads\": %d,\n", s.threads);
  std::fprintf(f, "  \"batch\": %d,\n", s.batch);
  std::fprintf(f, "  \"batch_calls\": %d,\n", s.batch_calls);
  std::fprintf(f, "  \"wall_seconds\": %.6f,\n", s.wall_seconds);
  std::fprintf(f, "  \"object_id_seconds\": %.6f,\n", s.object_id_seconds);
  if (o.chain == CHAIN_IMAGE) {
    /* The image chain starts at K = 0 and never resets, so its final K is the total. */
    std::fprintf(f, "  \"image_chain_final_k\": %llu,\n", (unsigned long long)s.total_k);
    std::fprintf(f,
                 "  \"image_chain_reached_vdc_period\": %s,\n",
                 s.total_k >= VDC_PERIOD ? "true" : "false");
  }
  else {
    std::fprintf(f, "  \"image_chain_final_k\": null,\n");
    std::fprintf(f, "  \"image_chain_reached_vdc_period\": null,\n");
  }
  std::fprintf(f, "  \"total_k_consumed\": %llu\n", (unsigned long long)s.total_k);
  std::fprintf(f, "}\n");
  return std::fclose(f) == 0;
}

int render_main(int argc, char **argv)
{
  Options o;
  o.threads = int(std::max(1u, std::thread::hardware_concurrency()));

  for (int a = 1; a < argc; ++a) {
    const std::string flag = argv[a];
    const bool known = flag == "--scene" || flag == "--size" || flag == "--passes" ||
                       flag == "--refr" || flag == "--seed" || flag == "--chain" ||
                       flag == "--halton" || flag == "--ghost" || flag == "--alpha" ||
                       flag == "--u2" || flag == "--continue-after-emitter" ||
                       flag == "--jitter" || flag == "--diffuse-gain" ||
                       flag == "--emission-gain" || flag == "--ray-epsilon" ||
                       flag == "--max-depth" || flag == "--threads" || flag == "--batch" ||
                       flag == "--out";
    if (!known) {
      return usage_error("unknown option '" + flag + "'");
    }
    if (a + 1 >= argc) {
      return usage_error("missing value for " + flag);
    }
    const std::string val = argv[++a];
    const std::string bad = "invalid value '" + val + "' for " + flag;
    unsigned long long uv = 0;
    double dv = 0;
    if (flag == "--scene") {
      if (val == "standalone") {
        return not_implemented(flag, val);
      }
      if (val != "gui") {
        return usage_error(bad);
      }
      o.scene = val;
    }
    else if (flag == "--size") {
      if (!parse_uint_arg(val, 1, INT_MAX, uv)) {
        return usage_error(bad);
      }
      o.size = int(uv);
    }
    else if (flag == "--passes") {
      if (!parse_uint_arg(val, 1, INT_MAX, uv)) {
        return usage_error(bad);
      }
      o.passes = int(uv);
    }
    else if (flag == "--refr") {
      if (!parse_double_arg(val, dv) || dv <= 0) {
        return usage_error(bad);
      }
      o.refr = dv;
    }
    else if (flag == "--seed") {
      if (!parse_uint_arg(val, 0, UINT32_MAX, uv)) {
        return usage_error(bad);
      }
      o.seed = uint32_t(uv);
    }
    else if (flag == "--chain") {
      const size_t colon = val.find(':');
      const std::string name = val.substr(0, colon);
      const bool has_param = colon != std::string::npos;
      const std::string arg = has_param ? val.substr(colon + 1) : std::string();
      if (!has_param && name == "image") {
        o.chain = CHAIN_IMAGE;
      }
      else if (!has_param && name == "row") {
        o.chain = CHAIN_ROW;
      }
      else if (has_param && name == "lane" && parse_uint_arg(arg, 1, INT_MAX, uv)) {
        o.chain = CHAIN_LANE;
        o.lane_length_requested = int(uv);
      }
      else if ((!has_param && name == "pixel-major") ||
               (has_param && (name == "omp-restart" || name == "pixel-major-omp") &&
                parse_uint_arg(arg, 1, INT_MAX, uv)))
      {
        return not_implemented(flag, val);
      }
      else {
        return usage_error(bad);
      }
      o.chain_text = val;
    }
    else if (flag == "--halton") {
      if (val == "incremental") {
        return not_implemented(flag, val);
      }
      if (val != "exact") {
        return usage_error(bad);
      }
      o.halton = val;
    }
    else if (flag == "--ghost") {
      if (val != "all" && val != "lights" && val != "none") {
        return usage_error(bad);
      }
      o.ghost = val;
    }
    else if (flag == "--alpha") {
      if (!parse_double_arg(val, dv)) {
        return usage_error(bad);
      }
      o.alpha = dv;
    }
    else if (flag == "--u2") {
      if (val == "base3") {
        return not_implemented(flag, val);
      }
      if (val != "same" && val != "independent") {
        return usage_error(bad);
      }
      o.u2 = val;
    }
    else if (flag == "--continue-after-emitter") {
      if (val != "yes" && val != "no") {
        return usage_error(bad);
      }
      o.continue_after_emitter = val;
    }
    else if (flag == "--jitter") {
      if (!parse_double_arg(val, dv)) {
        return usage_error(bad);
      }
      o.jitter = dv;
    }
    else if (flag == "--diffuse-gain") {
      if (!parse_double_arg(val, dv)) {
        return usage_error(bad);
      }
      o.diffuse_gain = dv;
    }
    else if (flag == "--emission-gain") {
      if (!parse_double_arg(val, dv)) {
        return usage_error(bad);
      }
      o.emission_gain = dv;
    }
    else if (flag == "--ray-epsilon") {
      if (!parse_double_arg(val, dv) || dv <= 0) {
        return usage_error(bad);
      }
      o.ray_epsilon = dv;
    }
    else if (flag == "--max-depth") {
      if (!parse_uint_arg(val, 1, INT_MAX, uv)) {
        return usage_error(bad);
      }
      o.max_depth = int(uv);
    }
    else if (flag == "--threads") {
      if (!parse_uint_arg(val, 1, INT_MAX, uv)) {
        return usage_error(bad);
      }
      o.threads = int(uv);
    }
    else if (flag == "--batch") {
      if (!parse_uint_arg(val, 1, INT_MAX, uv)) {
        return usage_error(bad);
      }
      o.batch = int(uv);
    }
    else if (flag == "--out") {
      o.out = val;
    }
  }
  if (o.out.empty()) {
    return usage_error("--out DIR is required");
  }

  /* The scene of SPEC §9 with the fixture's knobs, then every knob overridden from the CLI. A lane
   * longer than the row is one lane per row (lane_in_row 0), exactly as the oracle's clamp
   * min(L, n) (smallpaint_oracle.cpp:470-471); clamping also keeps the core's ceil(width / L) from
   * overflowing int for L near INT_MAX. */
  const int lane_length = (o.chain == CHAIN_LANE) ? std::min(o.lane_length_requested, o.size) :
                                                    1;
  SmallpaintSceneFixture scene(o.chain, lane_length);
  KernelPainterlyData &data = scene.data;
  data.cam.width = o.size;
  data.cam.height = o.size;
  data.cam.jitter = o.jitter;

  KernelPainterlyIntegrator &p = data.integrator;
  p.chain = o.chain;
  p.lane_length = lane_length;
  p.seed = o.seed;
  p.u2_mode = (o.u2 == "independent") ? U2_INDEPENDENT : U2_SAME;
  p.k0_phase_lock_bits = 0; /* SPEC §8 default; the oracle has no phase lock. */
  p.alpha = o.alpha;
  p.max_depth = o.max_depth;
  p.diffuse_gain = o.diffuse_gain;
  p.emission_gain = o.emission_gain;
  p.continue_after_emitter = (o.continue_after_emitter == "yes") ? 1 : 0;
  p.ray_epsilon = o.ray_epsilon;

  for (KernelPainterlyLobe &lobe : scene.lobes) {
    if (lobe.kind == LOBE_GLASS) {
      lobe.ior = o.refr;
    }
  }
  for (KernelPainterlyAnalytic &prim : scene.analytic) {
    if (prim.type != ANALYTIC_SPHERE) {
      continue;
    }
    const double3 E = scene.materials[size_t(prim.material)].emission;
    const bool emitter = E.x > 0 || E.y > 0 || E.z > 0;
    const bool ghost = (o.ghost == "all") || (o.ghost == "lights" && emitter);
    prim.intersection = ghost ? SPHERE_GHOST : SPHERE_EXACT;
  }

  RunStats stats;
  stats.lane_length = lane_length;
  PainterlyRenderBuffers buffers;
  try {
    PainterlyThreadPool pool(o.threads);
    stats.threads = pool.num_threads();
    buffers.reset(o.size, o.size);
    PainterlyPathTrace trace(scene.globals, buffers, pool);

    const auto id_start = std::chrono::steady_clock::now();
    trace.render_object_id();
    stats.object_id_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - id_start).count();

    /* A batch larger than the render is one call; 64-bit loop arithmetic avoids int overflow. */
    stats.batch = (o.batch == 0) ? o.passes : std::min(o.batch, o.passes);
    const std::atomic<bool> never_cancelled{false};
    for (int64_t begin64 = 0; begin64 < o.passes; begin64 += stats.batch) {
      const int begin = int(begin64);
      const int end = int(std::min<int64_t>(begin64 + stats.batch, o.passes));
      const auto start = std::chrono::steady_clock::now();
      const bool completed = trace.render_passes(begin, end, never_cancelled);
      stats.wall_seconds +=
          std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
      stats.batch_calls++;
      if (!completed) {
        std::fprintf(stderr, "painterly_render: render_passes(%d, %d) did not complete\n", begin, end);
        return 1;
      }
    }
    if (buffers.passes_done != o.passes) {
      std::fprintf(stderr,
                   "painterly_render: passes_done %d != passes %d\n",
                   buffers.passes_done,
                   o.passes);
      return 1;
    }
  }
  catch (const std::exception &e) {
    std::fprintf(stderr, "painterly_render: %s\n", e.what());
    return 1;
  }

  for (const uint64_t k : buffers.k_consumed) {
    stats.total_k += k;
  }

  const std::filesystem::path dir = o.out;
  std::error_code ec;
  std::filesystem::create_directories(dir, ec);
  if (ec) {
    return usage_error("cannot create output directory '" + o.out + "'");
  }

  /* PainterlyRenderBuffers stores pixel (row, col) at row * width + col with row 0 at the top and
   * three channels per pixel, which is the oracle's Film layout (smallpaint_oracle.cpp:349-355,
   * 371-375): the arrays are written as they are, with no reordering. */
  const std::vector<size_t> pixel_shape = {size_t(o.size), size_t(o.size)};
  const std::vector<size_t> rgb_shape = {size_t(o.size), size_t(o.size), size_t(PAINTERLY_CHANNELS)};
  bool ok = write_npy(dir / "sum.npy",
                      "<f8",
                      rgb_shape,
                      buffers.combined.data(),
                      buffers.combined.size() * sizeof(double));
  ok = write_npy(dir / "k_consumed.npy",
                 "<u8",
                 pixel_shape,
                 buffers.k_consumed.data(),
                 buffers.k_consumed.size() * sizeof(uint64_t)) &&
       ok;
  ok = write_npy(dir / "object_id.npy",
                 "<i4",
                 pixel_shape,
                 buffers.object_id.data(),
                 buffers.object_id.size() * sizeof(int32_t)) &&
       ok;
  ok = write_ppm(dir / "image.ppm", buffers, o.passes) && ok;
  ok = write_meta(dir / "meta.json", o, data, stats) && ok;
  if (!ok) {
    std::fprintf(stderr, "painterly_render: failed to write outputs to '%s'\n", o.out.c_str());
    return 1;
  }
  std::printf("painterly_render: wrote %s wall_seconds=%.3f total_k_consumed=%llu threads=%d "
              "batch=%d\n",
              o.out.c_str(),
              stats.wall_seconds,
              (unsigned long long)stats.total_k,
              stats.threads,
              stats.batch);
  return 0;
}

}  // namespace

CCL_NAMESPACE_END

int main(int argc, char **argv)
{
  return painterly::render_main(argc, argv);
}
