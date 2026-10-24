void ColorNode::compile(OSLCompiler &compiler)
{
  compiler.parameter_color("color_value", value);

  compiler.add(this, "node_value");
}
