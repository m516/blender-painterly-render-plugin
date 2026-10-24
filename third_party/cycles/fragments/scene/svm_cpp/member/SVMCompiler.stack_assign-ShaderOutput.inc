SVMStackOffset SVMCompiler::stack_assign(ShaderOutput *output)
{
  /* if no stack offset assigned yet, find one */
  if (output->stack_offset == SVM_STACK_INVALID) {
    output->stack_offset = stack_find_offset(output);
  }

  return output->stack_offset;
}
