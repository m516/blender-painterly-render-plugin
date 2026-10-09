/* Shim: replaces Cycles util/thread.h without TBB (upstream includes tbb/spin_mutex.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: thread_spin_lock is a std::atomic_flag spin lock with the
 * interface of tbb::spin_mutex (lock, try_lock, unlock), so this header needs no TBB. The rest of
 * the API is upstream's. */

#pragma once

#include <atomic>
#include <condition_variable>
#include <functional>
#include <mutex>
#include <thread>

#if defined(__APPLE__) || defined(__linux__) && !defined(__GLIBC__)
#  include <pthread.h>
#endif

#ifdef _WIN32
#  include "util/windows.h"
#endif

CCL_NAMESPACE_BEGIN

using thread_mutex = std::mutex;
using thread_scoped_lock = std::unique_lock<std::mutex>;
using thread_condition_variable = std::condition_variable;

/**
 * Own thread implementation similar to std::thread, so we can set a
 * custom stack size on macOS.
 */
class thread {
 public:
  thread(std::function<void()> run_cb);
  ~thread();

  static void *run(void *arg);
  bool join();

 protected:
  std::function<void()> run_cb_;
#if defined(__APPLE__) || defined(__linux__) && !defined(__GLIBC__)
  pthread_t pthread_id;
#else
  std::thread std_thread;
#endif
  bool joined_;
};

/* Spin lock with the interface of tbb::spin_mutex. */
class thread_spin_lock {
 public:
  void lock()
  {
    while (flag_.test_and_set(std::memory_order_acquire)) {
      std::this_thread::yield();
    }
  }

  bool try_lock()
  {
    return !flag_.test_and_set(std::memory_order_acquire);
  }

  void unlock()
  {
    flag_.clear(std::memory_order_release);
  }

 private:
  std::atomic_flag flag_{};
};

class thread_scoped_spin_lock {
 public:
  explicit thread_scoped_spin_lock(thread_spin_lock &lock) : lock_(lock)
  {
    lock_.lock();
  }

  ~thread_scoped_spin_lock()
  {
    lock_.unlock();
  }

  /* TODO(sergey): Implement manual control over lock/unlock. */

 protected:
  thread_spin_lock &lock_;
};

CCL_NAMESPACE_END
