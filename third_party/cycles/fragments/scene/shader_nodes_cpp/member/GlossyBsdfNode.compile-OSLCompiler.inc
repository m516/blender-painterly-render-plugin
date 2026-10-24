void GlossyBsdfNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "distribution");
  compiler.add(this, "node_glossy_bsdf");
}
