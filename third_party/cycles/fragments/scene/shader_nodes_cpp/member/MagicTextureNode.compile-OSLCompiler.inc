void MagicTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);

  compiler.parameter(this, "depth");
  compiler.add(this, "node_magic_texture");
}
