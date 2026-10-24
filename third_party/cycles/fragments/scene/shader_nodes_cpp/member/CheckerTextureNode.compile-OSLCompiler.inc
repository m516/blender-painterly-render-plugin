void CheckerTextureNode::compile(OSLCompiler &compiler)
{
  tex_mapping.compile(compiler);

  compiler.add(this, "node_checker_texture");
}
