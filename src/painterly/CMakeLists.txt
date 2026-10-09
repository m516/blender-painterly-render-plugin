# Engine layers, one add_subdirectory each. Later cards add their layer in dependency order: util, bvh, integrator,
# scene, session (docs/architecture.md "Dependency direction").
add_subdirectory(bvh)
