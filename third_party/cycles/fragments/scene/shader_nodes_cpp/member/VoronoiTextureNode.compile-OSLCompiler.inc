void VoronoiTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);

  compiler.parameter(this, "dimensions");
  compiler.parameter(this, "feature");
  compiler.parameter(this, "metric");
  compiler.parameter(this, "use_normalize");
  compiler.add(this, "node_voronoi_texture");
}
