# painterly_bvh: the triangle BVH over instanced meshes (T3.10). Embree is a private dependency: embree.h does not
# include Embree, so its symbols stay inside this static library and the consumers' headers never see them.
add_library(painterly_bvh STATIC embree.cpp)
target_link_libraries(painterly_bvh PUBLIC cycles_util PRIVATE painterly::embree)
