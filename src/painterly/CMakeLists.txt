# Engine layers, one add_subdirectory each, in dependency order: util, bvh, kernel, integrator, scene, session. kernel is
# the header-only painterly_kernel, which links painterly_bvh (docs/architecture.md "Dependency direction").
add_subdirectory(util)
add_subdirectory(bvh)
add_subdirectory(kernel)
add_subdirectory(integrator)
add_subdirectory(scene)
add_subdirectory(session)
