void RefractionBsdfNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "distribution");
  compiler.add(this, "node_refraction_bsdf");
}
