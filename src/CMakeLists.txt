add_subdirectory(cycles)

if(PAINTERLY_BUILD_MODULE)
  add_subdirectory(blender)
endif()

if(PAINTERLY_BUILD_TESTS)
  add_subdirectory(test)
endif()

if(PAINTERLY_BUILD_ORACLE)
  add_subdirectory(app)
endif()
