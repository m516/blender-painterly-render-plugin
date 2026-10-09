# The engine layers and the vendored Cycles libraries serve the module and the tests. The oracle needs neither.
if(PAINTERLY_BUILD_MODULE OR PAINTERLY_BUILD_TESTS)
  add_subdirectory(cycles)
  add_subdirectory(painterly)
endif()

if(PAINTERLY_BUILD_MODULE)
  add_subdirectory(blender)
endif()

if(PAINTERLY_BUILD_TESTS)
  add_subdirectory(test)
endif()

if(PAINTERLY_BUILD_ORACLE)
  add_subdirectory(app)
endif()
