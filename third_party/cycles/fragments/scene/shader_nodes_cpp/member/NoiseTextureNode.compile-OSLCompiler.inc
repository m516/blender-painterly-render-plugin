void NoiseTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);
  compiler.parameter(this, "dimensions");
  compiler.parameter(this, "type");
  compiler.parameter(this, "use_normalize");
  compiler.add(this, "node_noise_texture");
}
