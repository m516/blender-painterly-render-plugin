void TextureMapping::compile(OSLCompiler &compiler)
{
  if (!skip()) {
    compiler.parameter("mapping", compute_transform());
    compiler.parameter("use_mapping", 1);
  }
}
