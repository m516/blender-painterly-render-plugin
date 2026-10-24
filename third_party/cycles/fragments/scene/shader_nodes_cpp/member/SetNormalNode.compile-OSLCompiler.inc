void SetNormalNode::compile(OSLCompiler &compiler)
{
  compiler.add(this, "node_set_normal");
}
