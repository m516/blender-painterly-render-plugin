NODE_DEFINE(SetNormalNode)
{
  NodeType *type = NodeType::add("set_normal", create, NodeType::SHADER);

  SOCKET_IN_VECTOR(direction, "Direction", zero_float3());
  SOCKET_OUT_NORMAL(normal, "Normal");

  return type;
}
