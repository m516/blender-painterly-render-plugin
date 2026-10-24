void AddClosureNode::compile(OSLCompiler &compiler)
{
  compiler.add(this, "node_add_closure");
}
