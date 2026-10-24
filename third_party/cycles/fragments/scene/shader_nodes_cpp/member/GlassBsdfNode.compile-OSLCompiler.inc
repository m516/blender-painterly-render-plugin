void GlassBsdfNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "distribution");
  compiler.add(this, "node_glass_bsdf");
}
