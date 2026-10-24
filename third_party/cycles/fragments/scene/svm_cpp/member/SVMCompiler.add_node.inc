void SVMCompiler::add_node(ShaderNodeType type)
{
  svm_node_types_used[type] = true;
  current_svm_nodes.push_back_slow(type);
}
