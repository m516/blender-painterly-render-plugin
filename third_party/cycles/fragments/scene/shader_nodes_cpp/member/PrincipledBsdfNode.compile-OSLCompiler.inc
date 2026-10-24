void PrincipledBsdfNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "distribution");
  compiler.parameter(this, "subsurface_method");
  compiler.add(this, "node_principled_bsdf");
}
