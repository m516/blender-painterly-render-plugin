void TransparentBsdfNode::compile(OSLCompiler &compiler)
{
  compiler.add(this, "node_transparent_bsdf");
}
