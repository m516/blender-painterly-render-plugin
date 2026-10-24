void SVMCompiler::generate_node(ShaderNode *node, ShaderNodeSet &done)
{
  current_node = node;
  node->compile(*this);
  current_node = nullptr;
  stack_zero_incomplete_derivatives(node);
  stack_clear_users(node, done);
  stack_clear_temporary(node);

  if (current_type == SHADER_TYPE_SURFACE) {
    if (node->has_spatial_varying()) {
      current_shader->has_surface_spatial_varying = true;
    }
    if (node->get_feature() & KERNEL_FEATURE_NODE_RAYTRACE) {
      current_shader->has_surface_raytrace = true;
    }
  }
  else if (current_type == SHADER_TYPE_VOLUME) {
    if (node->has_spatial_varying()) {
      current_shader->has_volume_spatial_varying = true;
    }
    if (node->has_attribute_dependency()) {
      current_shader->has_volume_attribute_dependency = true;
    }
  }
}
