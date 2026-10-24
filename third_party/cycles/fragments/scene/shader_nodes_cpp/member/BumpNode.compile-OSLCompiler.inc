void BumpNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "invert");
  compiler.parameter(this, "use_object_space");
  compiler.add(this, "node_bump");
}
