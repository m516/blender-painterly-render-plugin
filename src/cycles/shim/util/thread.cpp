/* Shim: replaces Cycles util/thread.cpp without TBB (upstream's header util/thread.h includes
 * tbb/spin_mutex.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: copied from upstream util/thread.cpp, without its
 * util/system.h and util/windows.h includes. Nothing in this file calls a function from either:
 * util/thread.h already includes windows.h on Windows. The thread class and its stack size are
 * upstream's, so the behaviour is unchanged. */

#include "util/thread.h"

#if defined(__APPLE__) || defined(__linux__) && !defined(__GLIBC__)
#else
#  include <system_error>
#endif

CCL_NAMESPACE_BEGIN

thread::thread(std::function<void()> run_cb) : run_cb_(run_cb), joined_(false)
{
#if defined(__APPLE__) || defined(__linux__) && !defined(__GLIBC__)
  /* Set the stack size to 2MB to match GLIBC. The default 512KB on macOS is
   * too small for Embree, and consistent stack size also makes things more
   * predictable in general. */
  pthread_attr_t attribute;
  pthread_attr_init(&attribute);
  pthread_attr_setstacksize(&attribute, 1024 * 1024 * 2);
  pthread_create(&pthread_id, &attribute, run, (void *)this);
#else
  std_thread = std::thread(&thread::run, this);
#endif
}

thread::~thread()
{
  if (!joined_) {
    join();
  }
}

void *thread::run(void *arg)
{
  thread *self = (thread *)(arg);
  self->run_cb_();
  return nullptr;
}

bool thread::join()
{
  joined_ = true;
#if defined(__APPLE__) || defined(__linux__) && !defined(__GLIBC__)
  return pthread_join(pthread_id, nullptr) == 0;
#else
  try {
    std_thread.join();
    return true;
  }
  catch (const std::system_error &) {
    return false;
  }
#endif
}

CCL_NAMESPACE_END
