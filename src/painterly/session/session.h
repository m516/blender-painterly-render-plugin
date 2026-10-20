/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlySession: one asynchronous, cancellable render of a PainterlyScene snapshot (T3.14). It
 * is the C++ side of the pyi's Session: start() takes the snapshot on the caller thread
 * (PainterlyScene::device_update, docs/architecture.md "Dependency direction"), a worker thread
 * then drives PainterlyPathTrace batch by batch, and progress() and buffers_copy() report the last
 * finished batch under a mutex, so a reader never sees a half-written batch.
 *
 * The class is not parallel-safe: every method except progress(), buffers_copy() and wait() is for
 * the thread that called start(). progress(), buffers_copy() and wait() may be called from any
 * thread. Only one render runs at a time.
 *
 * Output is bit-identical for any thread count and batch size (SPEC §3, docs/architecture.md
 * "Determinism contract"), so the batches decide only how often the progress and the buffers are
 * published, and how promptly cancel() is observed. */

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <string>
#include <thread>

#include "painterly/integrator/buffers.h"
#include "painterly/scene/device_scene.h"
#include "painterly/util/thread_pool.h"

CCL_NAMESPACE_BEGIN

class PainterlyScene;

/* D13: the Python state strings are 'idle', 'rendering', 'done', 'cancelled' and 'error', in this
 * value order (_painterly.pyi, Session.progress). */
enum class PainterlySessionState {
  STATE_IDLE,
  STATE_RENDERING,
  STATE_DONE,
  STATE_CANCELLED,
  STATE_ERROR
};

/* One report of a session (_painterly.pyi, Session.progress).
 *   state:        the session's state;
 *   passes_done:  passes [0, passes_done) are in buffers_copy(), from the last finished batch;
 *   passes_total: the `passes` of the last start(), 0 before it;
 *   elapsed:      seconds from the start() that began this render to the moment of the report, or
 *                 to the finish of the render once it is no longer STATE_RENDERING;
 *   error:        what() of the exception that ended the render, empty otherwise. */
struct PainterlySessionProgress {
  PainterlySessionState state;
  int passes_done;
  int passes_total;
  double elapsed;
  std::string error;
};

class PainterlySession {
 public:
  /* Holds a reference to `scene` until start() takes the snapshot, so the scene must outlive the
   * session (T3.15: the Python Session keeps its Scene alive). `threads` is the size of the render
   * pool: 0 means std::thread::hardware_concurrency() (PainterlyThreadPool). Throws
   * std::invalid_argument for a negative count. Nothing is copied yet. */
  PainterlySession(const PainterlyScene &scene, int threads);
  /* Cancels a running render and joins its thread. */
  ~PainterlySession();

  PainterlySession(const PainterlySession &) = delete;
  PainterlySession &operator=(const PainterlySession &) = delete;

  /* Begins rendering `passes` passes asynchronously, `batch` passes per publication. The snapshot
   * is taken here, on the caller thread: scene.device_update(device_scene_) (which may throw, and
   * then leaves the session as it was), then a worker thread calls render_object_id() once and
   * render_passes(b, min(b + batch, passes)) per batch. After each batch it publishes passes_done
   * and a copy of the buffers.
   * Throws std::logic_error while a render is running, and std::invalid_argument for passes < 1 or
   * batch < 1. */
  void start(int passes, int batch);

  /* Blocks until the state is no longer STATE_RENDERING, or until `timeout_seconds` elapsed. A
   * negative timeout waits forever. Returns true when the state is no longer STATE_RENDERING. */
  bool wait(double timeout_seconds);

  /* Asks the render to stop. The worker observes the request between batches and between the
   * passes of a batch, and the session then reports STATE_CANCELLED with the passes_done of the
   * last finished batch. A cancel() outside a render changes no state; the next start() clears the
   * request. */
  void cancel();

  /* The current report, taken under the mutex (see PainterlySessionProgress for the units). */
  PainterlySessionProgress progress() const;

  /* A consistent copy of the buffers, taken under the mutex: it holds exactly the passes [0,
   * passes_done) of the last finished batch, never a half-written batch (T3.14). */
  PainterlyRenderBuffers buffers_copy() const;

 private:
  /* The worker thread: renders the passes of one start() and publishes after each batch. */
  void render(int passes, int batch);
  /* Copies the finished batch state into the published buffers, under the mutex. */
  void publish(const PainterlyRenderBuffers &buffers);
  /* Moves to a final state, records the elapsed time and wakes wait(). */
  void finish(PainterlySessionState state, std::string error);
  /* Seconds from the start of the current render. The caller holds mutex_. */
  double seconds_since_start() const;

  const PainterlyScene *scene_;
  /* The snapshot of start(); the render thread reads it through PainterlyGlobalsCPU. */
  PainterlyDeviceScene device_scene_;
  /* The render pool of `threads`. */
  PainterlyThreadPool pool_;

  /* Guards the fields below. The render thread writes them through publish() and finish(). */
  mutable std::mutex mutex_;
  std::condition_variable state_changed_;
  PainterlySessionState state_ = PainterlySessionState::STATE_IDLE;
  int passes_done_ = 0;
  int passes_total_ = 0;
  std::string error_;
  /* The buffers of the last finished batch. Only ever written under mutex_. */
  PainterlyRenderBuffers published_;
  std::chrono::steady_clock::time_point start_time_{};
  double elapsed_ = 0.0;

  /* The cancel request. std::atomic, so cancel() and the destructor set it without the mutex and
   * without waiting for a running batch. */
  std::atomic<bool> cancel_requested_{false};
  std::thread render_thread_;
};

CCL_NAMESPACE_END
