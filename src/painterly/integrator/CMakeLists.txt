# painterly_integrator: the lane scheduler and the film buffers (T3.12). It never includes painterly/session/
# (docs/architecture.md, "Dependency direction"); PainterlyScene::device_update() is the only bridge.
add_library(painterly_integrator STATIC buffers.cpp path_trace.cpp)
target_link_libraries(painterly_integrator PUBLIC painterly_util painterly_bvh)
