void EmissionNode::compile(OSLCompiler &compiler)
{
  compiler.add(this, "node_emission");
}
