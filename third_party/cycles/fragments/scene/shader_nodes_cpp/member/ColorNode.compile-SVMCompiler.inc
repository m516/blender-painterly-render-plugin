void ColorNode::compile(SVMCompiler &compiler)
{
  ShaderOutput *color_out = output("Color");

  if (!color_out->links.empty()) {
    compiler.add_value_node(this, value, compiler.output("Color"));
  }
}
