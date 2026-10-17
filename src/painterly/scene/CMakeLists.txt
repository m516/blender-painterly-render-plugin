# painterly_scene: the host scene (T3.13). It links cycles_graph (the Node reflection of
# PainterlyIntegrator), painterly_kernel (the header-only kernel INTERFACE target of TQ.1 F13, which
# links painterly_bvh and cycles_util; T3.22) and painterly_bvh (Embree). It never includes
# painterly/integrator/: PainterlyScene::device_update() hands the integrator plain kernel data
# (docs/architecture.md, "Dependency direction").
add_library(painterly_scene STATIC
  integrator.cpp
  camera.cpp
  background.cpp
  mesh.cpp
  scene.cpp
  device_scene.cpp)
target_link_libraries(painterly_scene PUBLIC cycles_graph painterly_kernel painterly_bvh)
painterly_target_warnings(painterly_scene)
