ConvertNode::ConvertNode(SocketType::Type from_, SocketType::Type to_, bool autoconvert)
    : ShaderNode(get_node_types()[from_][to_])
{
  from = from_;
  to = to_;

  if (from == to) {
    special_type = SHADER_SPECIAL_TYPE_PROXY;
  }
  else if (autoconvert) {
    special_type = SHADER_SPECIAL_TYPE_AUTOCONVERT;
  }
}
