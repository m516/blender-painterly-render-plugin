void ValueNode::compile(SVMCompiler &compiler)
{
  compiler.add_value_node(this, value, compiler.output("Value"));
}
