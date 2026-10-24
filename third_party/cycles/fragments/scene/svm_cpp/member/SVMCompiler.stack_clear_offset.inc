void SVMCompiler::stack_clear_offset(const ShaderIO *io, const SVMStackOffset offset)
{
  const int size = stack_size(io);

  for (int i = 0; i < size; i++) {
    active_stack.users[offset + i]--;
  }
}
