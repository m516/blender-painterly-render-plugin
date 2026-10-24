SVMCompiler::SVMCompiler(Scene *scene, Progress &progress) : scene(scene), progress(progress)
{
  max_stack_use = 0;
  current_type = SHADER_TYPE_SURFACE;
  current_shader = nullptr;
  current_graph = nullptr;
  background = false;
  mix_weight_offset = SVM_STACK_INVALID;
  bump_state_offset = SVM_STACK_INVALID;
  compile_failed = false;

  /* This struct has one entry for every node, in order of ShaderNodeType definition. */
  svm_node_types_used = (std::atomic_int *)&scene->dscene.data.svm_usage;
}
