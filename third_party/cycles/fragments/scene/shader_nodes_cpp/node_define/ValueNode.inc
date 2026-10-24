NODE_DEFINE(ValueNode)
{
  NodeType *type = NodeType::add("value", create, NodeType::SHADER);

  SOCKET_FLOAT(value, "Value", 0.0f);
  SOCKET_OUT_FLOAT(value, "Value");

  return type;
}
