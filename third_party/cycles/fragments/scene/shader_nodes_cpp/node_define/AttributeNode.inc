NODE_DEFINE(AttributeNode)
{
  NodeType *type = NodeType::add("attribute", create, NodeType::SHADER);

  SOCKET_STRING(attribute, "Attribute", ustring());

  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_VECTOR(vector, "Vector");
  SOCKET_OUT_FLOAT(fac, "Fac");
  SOCKET_OUT_FLOAT(alpha, "Alpha");

  return type;
}
