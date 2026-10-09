/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* A fixed pool of worker threads with a blocking parallel_for (T3.12). The pool decides only which
 * worker runs which item. Results must not depend on that choice: the path tracer gives every lane
 * its own pixels and its own K, and every worker its own scratch, so the output is bit-identical
 * for any thread count (docs/architecture.md, "Determinism contract"). */

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <vector>

#include "util/thread.h"

CCL_NAMESPACE_BEGIN

class PainterlyThreadPool {
 public:
  /* num_threads = 0 means std::thread::hardware_concurrency(), or 1 where that is unknown. Throws
   * std::invalid_argument for a negative count. */
  explicit PainterlyThreadPool(int num_threads);
  ~PainterlyThreadPool();

  PainterlyThreadPool(const PainterlyThreadPool &) = delete;
  PainterlyThreadPool &operator=(const PainterlyThreadPool &) = delete;

  int num_threads() const;

  /* Calls fn(index, worker) once for every index in [0, n) and returns when all calls have
   * finished. worker is in [0, num_threads()) and names the thread that runs the call. A worker
   * runs one call at a time. Items are claimed with an atomic counter, so the order of the calls
   * is unspecified. fn must not throw: an exception that escapes a worker thread terminates the
   * process. Calls to parallel_for must come from one thread at a time, and fn must not call
   * parallel_for on this pool. */
  void parallel_for(int64_t n, const std::function<void(int64_t index, int worker)> &fn);

 private:
  void worker_loop(int worker);
  /* Tells every worker to return from worker_loop. Each thread is joined by its destructor. */
  void request_stop();

  int num_threads_ = 0;
  std::vector<std::unique_ptr<thread>> workers_;

  /* Guards the job fields below. The workers sleep on work_ready_ and parallel_for sleeps on
   * work_done_. */
  std::mutex mutex_;
  std::condition_variable work_ready_;
  std::condition_variable work_done_;
  bool stop_ = false;
  /* Incremented once per parallel_for. A worker takes part in every generation exactly once,
   * because parallel_for waits until all workers have finished the previous one. */
  uint64_t generation_ = 0;
  int busy_workers_ = 0;
  int64_t n_ = 0;
  const std::function<void(int64_t, int)> *fn_ = nullptr;
  std::atomic<int64_t> next_{0};
};

CCL_NAMESPACE_END
