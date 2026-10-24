ShaderNodeType SVMCompiler::node_type(const ShaderNode *shader_node,
                                      const ShaderNodeType type,
                                      const bool use_derivatives)
{
  if ((use_derivatives || (shader_node && shader_node->need_derivatives())) &&
      current_type != SHADER_TYPE_VOLUME)
  {
    return svm_node_type_with_derivatives(type);
  }
  return type;
}
