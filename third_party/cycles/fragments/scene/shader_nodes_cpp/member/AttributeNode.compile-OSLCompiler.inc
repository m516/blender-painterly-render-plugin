void AttributeNode::compile(OSLCompiler &compiler)
{
  if (bump == SHADER_BUMP_DX) {
    compiler.parameter("bump_offset", "dx");
  }
  else if (bump == SHADER_BUMP_DY) {
    compiler.parameter("bump_offset", "dy");
  }
  else {
    compiler.parameter("bump_offset", "center");
  }
  compiler.parameter("bump_filter_width", bump_filter_width);

  if (Attribute::name_standard(attribute.c_str()) != ATTR_STD_NONE) {
    compiler.parameter("name", (string("geom:") + attribute.c_str()).c_str());
  }
  else {
    compiler.parameter("name", attribute.c_str());
  }

  compiler.add(this, "node_attribute");
}
