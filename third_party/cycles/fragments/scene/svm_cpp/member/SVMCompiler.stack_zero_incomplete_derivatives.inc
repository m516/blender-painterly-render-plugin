void SVMCompiler::stack_zero_incomplete_derivatives(const ShaderNode *node)
{
  /* No derivatives in volumes yet. */
  if (current_type == SHADER_TYPE_VOLUME) {
    return;
  }
  /* Does this node need derivatives but it doesn't have a derivative variation? */
  const bool incomplete_derivatives = node->need_derivatives() &&
                                      svm_node_type_with_derivatives(node->shader_node_type()) ==
                                          node->shader_node_type();
  if (!incomplete_derivatives) {
    return;
  }

  /* Zero derivatives. Note we can not use add_value_node since it will
   * automatically write derivatives. */
  for (const ShaderOutput *output : node->outputs) {
    if (output->stack_offset == SVM_STACK_INVALID) {
      continue;
    }
    const int base_size = stack_size(output->type());
    if (base_size == 3) {
      add_value_node(nullptr, zero_float3(), output->stack_offset + 3);
      add_value_node(nullptr, zero_float3(), output->stack_offset + 6);
    }
    else if (base_size == 1) {
      add_value_node(nullptr, 0.0f, output->stack_offset + 1);
      add_value_node(nullptr, 0.0f, output->stack_offset + 2);
    }
  }
}
