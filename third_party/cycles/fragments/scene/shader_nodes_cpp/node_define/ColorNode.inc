NODE_DEFINE(ColorNode)
{
  NodeType *type = NodeType::add("color", create, NodeType::SHADER);

  SOCKET_COLOR(value, "Value", zero_float3());
  SOCKET_OUT_COLOR(color, "Color");

  return type;
}
