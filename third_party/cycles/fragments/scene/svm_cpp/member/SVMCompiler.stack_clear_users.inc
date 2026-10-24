void SVMCompiler::stack_clear_users(ShaderNode *node, ShaderNodeSet &done)
{
  /* Possible minor optimization: If all nodes read all inputs before writing outputs,
   * the input stack space could be reused for the output and cache locality would be
   * improved. This was tried at some point but disabled, it would need careful validation
   * of stack assignment code and every SVM node implementation. It's not obvious if it's
   * worth it. */

  for (ShaderInput *input : node->inputs) {
    ShaderOutput *output = input->link;

    if (output && output->stack_offset != SVM_STACK_INVALID && is_sole_user(node, output, done)) {
      stack_clear_offset(output, output->stack_offset);
      output->stack_offset = SVM_STACK_INVALID;

      for (ShaderInput *in : output->links) {
        in->stack_offset = SVM_STACK_INVALID;
      }
    }
  }
}
