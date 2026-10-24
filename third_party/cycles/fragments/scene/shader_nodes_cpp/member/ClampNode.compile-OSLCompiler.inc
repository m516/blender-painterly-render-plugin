void ClampNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "clamp_type");
  compiler.add(this, "node_clamp");
}
