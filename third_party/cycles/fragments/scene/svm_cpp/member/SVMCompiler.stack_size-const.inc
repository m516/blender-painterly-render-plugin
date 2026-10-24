int SVMCompiler::stack_size(const ShaderIO *io)
{
  const SocketType::Type type = io->type();
  const bool derivative = io->parent->need_derivatives();

  return derivative ? stack_size(type) * 3 : stack_size(type);
}
