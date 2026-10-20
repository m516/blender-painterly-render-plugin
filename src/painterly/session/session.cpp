/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/session/session.h"

#include <algorithm>
#include <exception>
#include <stdexcept>
#include <string>
#include <utility>

#include "painterly/integrator/path_trace.h"
#include "painterly/scene/scene.h"

CCL_NAMESPACE_BEGIN

PainterlySession::PainterlySession(const PainterlyScene &scene, const int threads)
    : scene_(&scene), pool_(threads)
{
}

PainterlySession::~PainterlySession()
{
  cancel();
  /* The worker sets the final state before it returns, so the join also waits for the last
   * publish() and finish() to complete. */
  if (render_thread_.joinable()) {
    render_thread_.join();
  }
}

void PainterlySession::start(const int passes, const int batch)
{
  if (passes < 1) {
    throw std::invalid_argument("PainterlySession::start: passes must be >= 1");
  }
  if (batch < 1) {
    throw std::invalid_argument("PainterlySession::start: batch must be >= 1");
  }
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    if (state_ == PainterlySessionState::STATE_RENDERING) {
      throw std::logic_error("PainterlySession::start: a render is already running");
    }
  }
  /* A previous render has finished (or was never started): its thread must be joined before this
   * one replaces it, and before device_scene_ is overwritten, because the old thread reads it. */
  if (render_thread_.joinable()) {
    render_thread_.join();
  }

  /* The snapshot, on the caller thread (T3.14). It may throw, and then the session stays in the
   * state it had. */
  scene_->device_update(device_scene_);

  const KernelPainterlyCamera &cam = device_scene_.data.cam;
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    published_.reset(cam.width, cam.height);
    passes_done_ = 0;
    passes_total_ = passes;
    error_.clear();
    elapsed_ = 0.0;
    /* The cancel request is cleared before the state becomes STATE_RENDERING, so a cancel() that
     * happens after start() returned is never lost, and one from outside a render is not carried
     * into this one. */
    cancel_requested_.store(false);
    start_time_ = std::chrono::steady_clock::now();
    state_ = PainterlySessionState::STATE_RENDERING;
  }
  render_thread_ = std::thread(&PainterlySession::render, this, passes, batch);
}

bool PainterlySession::wait(const double timeout_seconds)
{
  std::unique_lock<std::mutex> lock(mutex_);
  const auto finished = [this] { return state_ != PainterlySessionState::STATE_RENDERING; };
  if (timeout_seconds < 0.0) {
    state_changed_.wait(lock, finished);
  }
  else {
    state_changed_.wait_for(lock, std::chrono::duration<double>(timeout_seconds), finished);
  }
  return state_ != PainterlySessionState::STATE_RENDERING;
}

void PainterlySession::cancel()
{
  cancel_requested_.store(true);
}

PainterlySessionProgress PainterlySession::progress() const
{
  const std::lock_guard<std::mutex> lock(mutex_);
  PainterlySessionProgress progress;
  progress.state = state_;
  progress.passes_done = passes_done_;
  progress.passes_total = passes_total_;
  progress.elapsed = (state_ == PainterlySessionState::STATE_RENDERING) ? seconds_since_start() :
                                                                          elapsed_;
  progress.error = error_;
  return progress;
}

PainterlyRenderBuffers PainterlySession::buffers_copy() const
{
  const std::lock_guard<std::mutex> lock(mutex_);
  return published_;
}

void PainterlySession::render(const int passes, const int batch)
{
  try {
    const PainterlyGlobalsCPU kg = device_scene_.globals();
    /* The working buffers of the render thread. published_ only ever receives finished batches. */
    PainterlyRenderBuffers buffers;
    buffers.reset(kg.data->cam.width, kg.data->cam.height);
    PainterlyPathTrace trace(kg, buffers, pool_);
    trace.render_object_id();
    for (int pass_begin = 0; pass_begin < passes; pass_begin += batch) {
      if (cancel_requested_.load()) {
        finish(PainterlySessionState::STATE_CANCELLED, std::string());
        return;
      }
      const int pass_end = std::min(pass_begin + batch, passes);
      if (!trace.render_passes(pass_begin, pass_end, cancel_requested_)) {
        /* A pass of this batch saw the cancel request: passes_done stays at the last finished
         * batch, so the published buffers are consistent (T3.12, render_passes). */
        finish(PainterlySessionState::STATE_CANCELLED, std::string());
        return;
      }
      publish(buffers);
    }
  }
  catch (const std::exception &e) {
    finish(PainterlySessionState::STATE_ERROR, e.what());
    return;
  }
  catch (...) {
    finish(PainterlySessionState::STATE_ERROR, "unknown exception");
    return;
  }
  finish(PainterlySessionState::STATE_DONE, std::string());
}

void PainterlySession::publish(const PainterlyRenderBuffers &buffers)
{
  const std::lock_guard<std::mutex> lock(mutex_);
  published_ = buffers;
  passes_done_ = buffers.passes_done;
}

void PainterlySession::finish(const PainterlySessionState state, std::string error)
{
  {
    const std::lock_guard<std::mutex> lock(mutex_);
    state_ = state;
    error_ = std::move(error);
    elapsed_ = seconds_since_start();
  }
  state_changed_.notify_all();
}

double PainterlySession::seconds_since_start() const
{
  const std::chrono::duration<double> elapsed = std::chrono::steady_clock::now() - start_time_;
  return elapsed.count();
}

CCL_NAMESPACE_END
