SVMStackOffset TextureMapping::compile_begin(SVMCompiler &compiler,
                                             ShaderInput *vector_in,
                                             ShaderNode *node)
{
  if (!skip()) {
    const SVMStackOffset offset_in = compiler.stack_assign(vector_in);
    assert(vector_in->type() == SocketType::VECTOR || vector_in->type() == SocketType::POINT);
    const SVMStackOffset offset_out = compiler.stack_find_offset(vector_in);

    compile(compiler, offset_in, offset_out, node);

    return offset_out;
  }

  return compiler.stack_assign(vector_in);
}
