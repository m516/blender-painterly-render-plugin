void GradientTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);

  compiler.parameter(this, "gradient_type");
  compiler.add(this, "node_gradient_texture");
}
