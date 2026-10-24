void SVMCompiler::stack_link(ShaderInput *input, ShaderOutput *output)
{
  if (output->stack_offset == SVM_STACK_INVALID) {
    assert(input->link);
    assert(stack_size(output->type()) == stack_size(input->link->type()));

    output->stack_offset = input->link->stack_offset;
    const int size = stack_size(output);

    for (int i = 0; i < size; i++) {
      active_stack.users[output->stack_offset + i]++;
    }
  }
}
