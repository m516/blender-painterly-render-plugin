NODE_DEFINE(OutputNode)
{
  NodeType *type = NodeType::add("output", create, NodeType::SHADER);

  SOCKET_IN_CLOSURE(surface, "Surface");
  SOCKET_IN_CLOSURE(volume, "Volume");
  SOCKET_IN_VECTOR(displacement, "Displacement", zero_float3());
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3());

  return type;
}
