find_package(Threads REQUIRED)

add_executable(smallpaint_oracle smallpaint_oracle.cpp)
target_link_libraries(smallpaint_oracle PRIVATE Threads::Threads)
