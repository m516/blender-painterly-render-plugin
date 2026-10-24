void TextureMapping::compile_end(SVMCompiler &compiler,
                                 ShaderInput *vector_in,
                                 const SVMStackOffset vector_offset)
{
  if (!skip()) {
    compiler.stack_clear_offset(vector_in, vector_offset);
  }
}
