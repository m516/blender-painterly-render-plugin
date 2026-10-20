# painterly_session: the asynchronous, cancellable render session (T3.14). It links painterly_integrator
# (PainterlyPathTrace, PainterlyRenderBuffers) and painterly_scene (PainterlyScene, PainterlyDeviceScene): the
# session is the only layer that includes both (docs/architecture.md, "Dependency direction"). The thread pool
# reaches it through painterly_integrator's painterly_util.
add_library(painterly_session STATIC session.cpp)
target_link_libraries(painterly_session PUBLIC painterly_integrator painterly_scene)
painterly_target_warnings(painterly_session)
