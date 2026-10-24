void SVMCompiler::generate_closure_node(ShaderNode *node, CompilerState *state)
{
  /* Skip generating closure that are not supported or needed for a particular
   * type of shader. For example a BSDF in a volume shader. */
  const uint node_feature = node->get_feature();
  if ((state->node_feature_mask & node_feature) != node_feature) {
    return;
  }

  /* execute dependencies for closure */
  for (ShaderInput *in : node->inputs) {
    if (in->link != nullptr) {
      ShaderNodeSet dependencies;
      find_dependencies(dependencies, state->nodes_done, in);
      generate_svm_nodes(dependencies, state);
    }
  }

  /* closure mix weight */
  const char *weight_name = (current_type == SHADER_TYPE_VOLUME) ? "VolumeMixWeight" :
                                                                   "SurfaceMixWeight";
  ShaderInput *weight_in = node->input(weight_name);

  if (weight_in && (weight_in->link || node->get_float(weight_in->socket_type) != 1.0f)) {
    mix_weight_offset = stack_assign(weight_in);
  }
  else {
    mix_weight_offset = SVM_STACK_INVALID;
  }

  /* compile closure itself */
  generate_node(node, state->nodes_done);

  mix_weight_offset = SVM_STACK_INVALID;

  if (current_type == SHADER_TYPE_SURFACE) {
    if (node->has_surface_transparent()) {
      current_shader->has_surface_transparent = true;
    }
    if (node->has_surface_bssrdf()) {
      current_shader->has_surface_bssrdf = true;
      if (node->has_bssrdf_bump()) {
        current_shader->has_bssrdf_bump = true;
      }
    }
    if (node->has_bump()) {
      current_shader->has_bump_from_surface = true;
    }
  }
}
