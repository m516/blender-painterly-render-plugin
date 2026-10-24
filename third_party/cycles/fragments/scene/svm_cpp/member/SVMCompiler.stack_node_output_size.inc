int SVMCompiler::stack_node_output_size(const ShaderNode *node)
{
  /* Compute stack size that will be allocated by this node. */
  int size = 0;
  for (const ShaderOutput *output : node->outputs) {
    if (!output->links.empty() && output->stack_offset == SVM_STACK_INVALID) {
      size += stack_size(output);
    }
  }
  return size;
}
