/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Tests of painterly/session/ (T3.14): the asynchronous, cancellable render session. The scene is
// the 32 x 32 analytic smallpaint reference of SPEC §9, built through the PainterlyScene API
// (add_material / add_sphere / add_plane / set_camera_smallpaint), so the results do not depend on
// the ISA. The session's buffers are compared bit for bit with a direct PainterlyPathTrace run
// (memcmp compares representations, so -0.0 and +0.0 differ). No tolerance appears.
//
// The cancel latency is recorded and printed, with no threshold (D27): it is the wall-clock time
// from cancel() to the return of wait(), and nothing asserts a bound on it.

#include <doctest/doctest.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <vector>

#include "painterly/integrator/buffers.h"
#include "painterly/integrator/path_trace.h"
#include "painterly/kernel/types.h"
#include "painterly/scene/device_scene.h"
#include "painterly/scene/scene.h"
#include "painterly/session/session.h"
#include "painterly/util/math_double3.h"
#include "painterly/util/thread_pool.h"

CCL_NAMESPACE_BEGIN

namespace {

/* The image of the card's test scene: 32 x 32 pixels. */
constexpr int WIDTH = 32;
constexpr int HEIGHT = 32;
/* The render pool of the session and of the direct comparison run. Any count gives the same bits
 * (SPEC §3); 2 is enough to make the pool real and keeps the test inside its time budget. */
constexpr int THREADS = 2;

/* SPEC §9: the reference scene's ten objects, in list order. Their ids are the list positions. */
constexpr int LIGHT_OBJECT_ID = 9;
/* SPEC §9 table: light emission 120 (smallpaint_painterly.cpp:262). */
constexpr double LIGHT_EMISSION = 120.0;
/* SPEC §9: glass IOR 1.5 (GUI default, refr_index). */
constexpr double GLASS_IOR = 1.5;

/* SPEC §8 knob values of the reference, as smallpaint_scene_fixture.h (D10) writes them: the gains
 * and epsilon are double(0.1f) and double(1e-4f), the float values the sockets hold. */
constexpr double DIFFUSE_GAIN = double(0.1f);
constexpr double RAY_EPSILON = double(1e-4f);
/* smallpaint_painterly.cpp:190. */
constexpr int MAX_DEPTH = 20;

/* The render of the STATE_DONE test: 8 passes in batches of 3, so the last batch is clipped from
 * 3 passes to the 2 that are left (min(b + batch, passes), T3.14). */
constexpr int DONE_PASSES = 8;
constexpr int DONE_BATCH = 3;

/* The render the cancel test interrupts: 1000 passes, the count of the T3.14 card, in batches of 1
 * (the pyi's default). It takes far longer than the cancel latency, so the cancel always lands
 * while the render is running. */
constexpr int CANCEL_PASSES = 1000;
constexpr int CANCEL_BATCH = 1;

/* How often the tests poll progress() while they wait for the first batch, in seconds. It only
 * bounds the waiting loop; the loop leaves as soon as the condition holds. */
constexpr double POLL_SECONDS = 0.001;
/* The longest a test waits for the first finished batch before it goes on anyway, in seconds. It
 * keeps a broken session from hanging the suite; on this machine the first batch of a 32 x 32
 * render finishes in milliseconds. */
constexpr double ARM_SECONDS = 60.0;

/* A material with one constant lobe (painterly/scene/material.h). */
KernelPainterlyLobe lobe(const int kind, const double3 weight, const double ior)
{
  KernelPainterlyLobe l{};
  l.kind = kind;
  l.weight = weight;
  l.ior = ior;
  return l;
}

/* The smallpaint reference scene of SPEC §9 through the PainterlyScene API, with the knob values
 * of the reference (SPEC §8). The materials are the ones smallpaint_scene_fixture.h (D10) builds:
 * white weights for the mirror and the glass, `cl` for the diffuse surfaces. */
void build_reference_scene(PainterlyScene &scene)
{
  const double3 white = make_double3(1.0);
  const double3 black = make_double3(0.0);

  /* SPEC §9, in list order: material i belongs to object i. */
  const int middle_sphere = scene.add_material({lobe(LOBE_MIRROR, white, 0.0)}, black);
  const int right_sphere = scene.add_material({lobe(LOBE_GLASS, white, GLASS_IOR)}, black);
  const int left_sphere = scene.add_material(
      {lobe(LOBE_DIFFUSE, make_double3(4.0, 4.0, 12.0), 0.0)}, black);
  const int bottom = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int back = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int left = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(10.0, 2.0, 2.0), 0.0)},
                                      black);
  const int right = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(2.0, 10.0, 2.0), 0.0)},
                                       black);
  const int ceiling = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int front = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int light = scene.add_material({lobe(LOBE_DIFFUSE, black, 0.0)},
                                       make_double3(LIGHT_EMISSION));

  /* Object ids are the list positions, as the running counter gives them (SPEC §9). */
  scene.add_sphere(
      make_double3(1.45, -0.75, -4.4), 1.05, middle_sphere, SPHERE_GHOST, -1, nullptr);
  scene.add_sphere(make_double3(2.05, 2.0, -3.7), 0.5, right_sphere, SPHERE_GHOST, -1, nullptr);
  scene.add_sphere(make_double3(1.95, -1.75, -3.1), 0.6, left_sphere, SPHERE_GHOST, -1, nullptr);
  scene.add_plane(make_double3(-1.0, 0.0, 0.0), 2.5, bottom, -1);
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 5.5, back, -1);
  scene.add_plane(make_double3(0.0, 1.0, 0.0), 2.75, left, -1);
  scene.add_plane(make_double3(0.0, -1.0, 0.0), 2.75, right, -1);
  scene.add_plane(make_double3(1.0, 0.0, 0.0), 3.0, ceiling, -1);
  scene.add_plane(make_double3(0.0, 0.0, -1.0), 0.5, front, -1);
  scene.add_sphere(make_double3(-1.9, 0.0, -3.0), 0.5, light, SPHERE_GHOST, -1, nullptr);

  /* SPEC §7, §8: the reference camera and the reference knobs. */
  scene.set_camera_smallpaint(WIDTH, HEIGHT);
  scene.integrator.set_chain(CHAIN_ROW);
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_SMALLPAINT);
  scene.integrator.set_max_depth(MAX_DEPTH);
  scene.integrator.set_diffuse_gain(float(DIFFUSE_GAIN));
  scene.integrator.set_ray_epsilon(float(RAY_EPSILON));
}

/* True when `p` reports a finished render. */
bool finished(const PainterlySessionProgress &p)
{
  return p.state != PainterlySessionState::STATE_RENDERING;
}

/* Polls progress() until at least one pass is published, the render is finished, or ARM_SECONDS
 * elapsed. Returns the last report. */
PainterlySessionProgress wait_for_first_batch(const PainterlySession &session)
{
  const auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::duration<double>(ARM_SECONDS);
  PainterlySessionProgress p = session.progress();
  while (p.passes_done == 0 && !finished(p) && std::chrono::steady_clock::now() < deadline) {
    std::this_thread::sleep_for(std::chrono::duration<double>(POLL_SECONDS));
    p = session.progress();
  }
  return p;
}

/* Renders the scene directly, in the same batches as the session: object ids once, then the passes
 * batch by batch (T3.14). This is the reference the session's buffers must equal. */
PainterlyRenderBuffers render_directly(const PainterlyScene &scene,
                                       const int passes,
                                       const int batch)
{
  PainterlyDeviceScene ds;
  scene.device_update(ds);
  PainterlyThreadPool pool(THREADS);
  PainterlyRenderBuffers buffers;
  buffers.reset(ds.data.cam.width, ds.data.cam.height);
  /* PainterlyPathTrace keeps the address of the globals it is given, so they live in a local. */
  const PainterlyGlobalsCPU kg = ds.globals();
  PainterlyPathTrace trace(kg, buffers, pool);
  trace.render_object_id();
  const std::atomic<bool> never_cancelled{false};
  for (int pass_begin = 0; pass_begin < passes; pass_begin += batch) {
    const int pass_end = std::min(pass_begin + batch, passes);
    REQUIRE(trace.render_passes(pass_begin, pass_end, never_cancelled));
  }
  return buffers;
}

/* Checks that two buffer sets hold the same size, the same pass count and the same bits. */
void check_buffers_equal(const PainterlyRenderBuffers &actual,
                         const PainterlyRenderBuffers &expected)
{
  CHECK(actual.width == expected.width);
  CHECK(actual.height == expected.height);
  CHECK(actual.passes_done == expected.passes_done);
  REQUIRE(actual.combined.size() == expected.combined.size());
  REQUIRE(actual.k_consumed.size() == expected.k_consumed.size());
  REQUIRE(actual.object_id.size() == expected.object_id.size());
  CHECK(std::memcmp(actual.combined.data(),
                    expected.combined.data(),
                    actual.combined.size() * sizeof(double)) == 0);
  CHECK(std::memcmp(actual.k_consumed.data(),
                    expected.k_consumed.data(),
                    actual.k_consumed.size() * sizeof(uint64_t)) == 0);
  CHECK(std::memcmp(actual.object_id.data(),
                    expected.object_id.data(),
                    actual.object_id.size() * sizeof(int32_t)) == 0);
}

}  // namespace

TEST_CASE("painterly session: start and wait render every pass and match a direct run")
{
  PainterlyScene scene;
  build_reference_scene(scene);
  PainterlySession session(scene, THREADS);

  /* Nothing is rendered before start(): the pyi's 'idle' (D13). */
  const PainterlySessionProgress idle = session.progress();
  CHECK(idle.state == PainterlySessionState::STATE_IDLE);
  CHECK(idle.passes_done == 0);
  CHECK(idle.passes_total == 0);
  CHECK(idle.error.empty());

  session.start(DONE_PASSES, DONE_BATCH);
  /* wait() with a negative timeout waits forever (T3.14). */
  CHECK(session.wait(-1.0));

  const PainterlySessionProgress done = session.progress();
  CHECK(done.state == PainterlySessionState::STATE_DONE);
  CHECK(done.passes_done == DONE_PASSES);
  CHECK(done.passes_total == DONE_PASSES);
  CHECK(done.error.empty());
  /* The elapsed time of a finished render is positive and no longer grows. */
  CHECK(done.elapsed > 0.0);

  /* The published buffers are exactly the passes of the last finished batch, bit for bit equal to
   * a direct PainterlyPathTrace run of the same scene in the same batches. */
  const PainterlyRenderBuffers buffers = session.buffers_copy();
  CHECK(buffers.passes_done == DONE_PASSES);
  check_buffers_equal(buffers, render_directly(scene, DONE_PASSES, DONE_BATCH));

  /* The object-id buffer holds the reference scene's ids: the light is object 9 (SPEC §9) and the
   * scene is closed, so no pixel keeps the miss value. */
  bool saw_light = false;
  for (const int32_t id : buffers.object_id) {
    CHECK(id >= 0);
    saw_light = saw_light || (id == LIGHT_OBJECT_ID);
  }
  CHECK(saw_light);
}

TEST_CASE("painterly session: start while rendering throws std::logic_error")
{
  PainterlyScene scene;
  build_reference_scene(scene);
  PainterlySession session(scene, THREADS);
  session.start(CANCEL_PASSES, CANCEL_BATCH);
  /* The state is STATE_RENDERING from the return of start() until the render finishes, so this
   * check does not race with the worker: only the worker leaves that state. */
  CHECK_THROWS_AS(session.start(DONE_PASSES, DONE_BATCH), std::logic_error);
  session.cancel();
  CHECK(session.wait(-1.0));
}

TEST_CASE("painterly session: cancel stops the render and records its latency")
{
  PainterlyScene scene;
  build_reference_scene(scene);
  PainterlySession session(scene, THREADS);

  session.start(CANCEL_PASSES, CANCEL_BATCH);
  /* Let the render publish its first batch, so that the cancel really lands during a render. */
  const PainterlySessionProgress armed = wait_for_first_batch(session);
  REQUIRE_FALSE(finished(armed));
  REQUIRE(armed.passes_done > 0);

  const auto cancel_time = std::chrono::steady_clock::now();
  session.cancel();
  CHECK(session.wait(-1.0));
  const std::chrono::duration<double> latency = std::chrono::steady_clock::now() - cancel_time;

  const PainterlySessionProgress cancelled = session.progress();
  CHECK(cancelled.state == PainterlySessionState::STATE_CANCELLED);
  CHECK(cancelled.passes_total == CANCEL_PASSES);
  CHECK(cancelled.passes_done < CANCEL_PASSES);
  /* A cancelled render keeps the passes of its last finished batch, so its buffers hold exactly
   * that many passes and equal a direct run of them. The direct run takes them in one batch: the
   * output is bit-identical for any batching (SPEC §3, docs/architecture.md "Determinism
   * contract"), so this also proves that the cancellation kept no partial batch. How many passes
   * the finished batches hold depends on the machine's timing, so the run is one batch of
   * `passes_done` passes and the assertion count does not depend on that number. */
  const PainterlyRenderBuffers buffers = session.buffers_copy();
  CHECK(buffers.passes_done == cancelled.passes_done);
  check_buffers_equal(buffers,
                      render_directly(scene, cancelled.passes_done, cancelled.passes_done));

  /* D27: the latency is recorded and reported, with no threshold. */
  std::cout << "painterly session: cancel latency " << latency.count() << " s, passes_done "
            << cancelled.passes_done << " of " << CANCEL_PASSES << std::endl;
}

TEST_CASE("painterly session: the destructor cancels and joins a running render")
{
  PainterlyScene scene;
  build_reference_scene(scene);
  {
    PainterlySession session(scene, THREADS);
    session.start(CANCEL_PASSES, CANCEL_BATCH);
    const PainterlySessionProgress armed = wait_for_first_batch(session);
    REQUIRE_FALSE(finished(armed));
    /* The destructor cancels the render and joins its thread, so it returns only after the worker
     * has stopped. Nothing may hang, crash or touch the scene after this point. */
  }
  /* The scene is untouched and usable: a second session on it renders to completion, which it
   * could not if the first session's thread were still running or had left the scene half
   * updated. */
  PainterlySession second(scene, THREADS);
  second.start(DONE_PASSES, DONE_BATCH);
  CHECK(second.wait(-1.0));
  CHECK(second.progress().state == PainterlySessionState::STATE_DONE);
  CHECK(second.progress().passes_done == DONE_PASSES);
}

TEST_CASE("painterly session: an exception on the render thread becomes STATE_ERROR")
{
  PainterlyScene scene;
  build_reference_scene(scene);
  /* max_depth 0 is a kernel precondition that PainterlyPathTrace's constructor rejects (TQ.1 F8).
   * device_update accepts it, so the throw happens on the render thread. */
  scene.integrator.set_max_depth(0);
  PainterlySession session(scene, THREADS);
  session.start(DONE_PASSES, DONE_BATCH);
  CHECK(session.wait(-1.0));

  const PainterlySessionProgress failed = session.progress();
  CHECK(failed.state == PainterlySessionState::STATE_ERROR);
  CHECK(failed.passes_done == 0);
  CHECK(failed.passes_total == DONE_PASSES);
  CHECK(failed.error.find("max_depth") != std::string::npos);
}

CCL_NAMESPACE_END
