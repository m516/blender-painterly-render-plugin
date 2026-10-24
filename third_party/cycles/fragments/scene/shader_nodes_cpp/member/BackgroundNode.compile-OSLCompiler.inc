void BackgroundNode::compile(OSLCompiler &compiler)
{
  compiler.add(this, "node_background");
}
