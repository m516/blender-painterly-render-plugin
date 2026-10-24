void SVMCompiler::find_dependencies(ShaderNodeSet &dependencies,
                                    const ShaderNodeSet &done,
                                    ShaderInput *input,
                                    ShaderNode *skip_node)
{
  ShaderNode *node = (input->link) ? input->link->parent : nullptr;
  if (node != nullptr && !done.contains(node) && node != skip_node && !dependencies.contains(node))
  {
    for (ShaderInput *in : node->inputs) {
      find_dependencies(dependencies, done, in, skip_node);
    }
    dependencies.insert(node);
  }
}
