# painterly_util: the deterministic thread pool (T3.12). Its workers are Cycles' util/thread shim (T3.3, 2 MB stacks).
add_library(painterly_util STATIC thread_pool.cpp)
target_link_libraries(painterly_util PUBLIC cycles_util)
