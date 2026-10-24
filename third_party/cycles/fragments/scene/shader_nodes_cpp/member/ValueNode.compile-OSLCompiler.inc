void ValueNode::compile(OSLCompiler &compiler)
{
  compiler.parameter("value_value", value);
  compiler.add(this, "node_value");
}
