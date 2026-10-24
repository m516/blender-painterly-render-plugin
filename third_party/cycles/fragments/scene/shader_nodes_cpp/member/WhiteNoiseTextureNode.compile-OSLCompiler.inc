void WhiteNoiseTextureNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "dimensions");
  compiler.add(this, "node_white_noise_texture");
}
