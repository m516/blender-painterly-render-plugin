void DiffuseBsdfNode::compile(OSLCompiler &compiler)
{
  compiler.add(this, "node_diffuse_bsdf");
}
