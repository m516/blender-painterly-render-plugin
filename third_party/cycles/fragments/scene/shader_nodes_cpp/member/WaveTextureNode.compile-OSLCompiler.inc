void WaveTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);

  compiler.parameter(this, "wave_type");
  compiler.parameter(this, "bands_direction");
  compiler.parameter(this, "rings_direction");
  compiler.parameter(this, "profile");

  compiler.add(this, "node_wave_texture");
}
