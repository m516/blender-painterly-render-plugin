void SVMCompiler::stack_clear_temporary(ShaderNode *node)
{
  for (ShaderInput *input : node->inputs) {
    if (!input->link && input->stack_offset != SVM_STACK_INVALID) {
      stack_clear_offset(input, input->stack_offset);
      input->stack_offset = SVM_STACK_INVALID;
    }
  }
}
