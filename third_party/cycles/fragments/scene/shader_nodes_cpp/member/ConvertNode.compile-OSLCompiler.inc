void ConvertNode::compile(OSLCompiler &compiler)
{
  /* proxy nodes should have been removed at this point */
  assert(special_type != SHADER_SPECIAL_TYPE_PROXY);

  if (from == SocketType::FLOAT) {
    compiler.add(this, "node_convert_from_float");
  }
  else if (from == SocketType::INT) {
    compiler.add(this, "node_convert_from_int");
  }
  else if (from == SocketType::COLOR) {
    compiler.add(this, "node_convert_from_color");
  }
  else if (from == SocketType::VECTOR) {
    compiler.add(this, "node_convert_from_vector");
  }
  else if (from == SocketType::POINT) {
    compiler.add(this, "node_convert_from_point");
  }
  else if (from == SocketType::NORMAL) {
    compiler.add(this, "node_convert_from_normal");
  }
  else {
    assert(0);
  }
}
