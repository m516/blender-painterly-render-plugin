/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/util/thread_pool.h"

#include <algorithm>
#include <stdexcept>
#include <thread>

CCL_NAMESPACE_BEGIN

PainterlyThreadPool::PainterlyThreadPool(const int num_threads)
{
  if (num_threads < 0) {
    throw std::invalid_argument("PainterlyThreadPool: num_threads must be >= 0");
  }
  int count = num_threads;
  if (count == 0) {
    /* hardware_concurrency() returns 0 when the count is unknown. One thread is the fallback. */
    count = std::max(int(std::thread::hardware_concurrency()), 1);
  }
  num_threads_ = count;
  workers_.reserve(count);
  try {
    for (int worker = 0; worker < count; worker++) {
      workers_.push_back(std::make_unique<thread>([this, worker] { worker_loop(worker); }));
    }
  }
  catch (...) {
    /* The started workers would wait forever for work, and their destructors would then hang. */
    request_stop();
    throw;
  }
}

PainterlyThreadPool::~PainterlyThreadPool()
{
  request_stop();
  /* Each thread joins in its destructor (util/thread.cpp). */
  workers_.clear();
}

void PainterlyThreadPool::request_stop()
{
  {
    std::lock_guard<std::mutex> lock(mutex_);
    stop_ = true;
  }
  work_ready_.notify_all();
}

int PainterlyThreadPool::num_threads() const
{
  return num_threads_;
}

void PainterlyThreadPool::parallel_for(const int64_t n,
                                       const std::function<void(int64_t, int)> &fn)
{
  if (n <= 0) {
    return;
  }
  {
    std::lock_guard<std::mutex> lock(mutex_);
    fn_ = &fn;
    n_ = n;
    next_.store(0);
    busy_workers_ = num_threads_;
    generation_++;
  }
  work_ready_.notify_all();

  std::unique_lock<std::mutex> lock(mutex_);
  work_done_.wait(lock, [this] { return busy_workers_ == 0; });
  fn_ = nullptr;
}

void PainterlyThreadPool::worker_loop(const int worker)
{
  uint64_t seen = 0;
  for (;;) {
    std::unique_lock<std::mutex> lock(mutex_);
    work_ready_.wait(lock, [this, seen] { return stop_ || generation_ != seen; });
    if (stop_) {
      return;
    }
    seen = generation_;
    const std::function<void(int64_t, int)> *fn = fn_;
    const int64_t n = n_;
    lock.unlock();

    for (int64_t index = next_.fetch_add(1); index < n; index = next_.fetch_add(1)) {
      (*fn)(index, worker);
    }

    lock.lock();
    busy_workers_--;
    if (busy_workers_ == 0) {
      work_done_.notify_one();
    }
  }
}

CCL_NAMESPACE_END
