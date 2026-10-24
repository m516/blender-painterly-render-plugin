void BrickTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);

  compiler.parameter(this, "offset");
  compiler.parameter(this, "offset_frequency");
  compiler.parameter(this, "squash");
  compiler.parameter(this, "squash_frequency");
  compiler.add(this, "node_brick_texture");
}
