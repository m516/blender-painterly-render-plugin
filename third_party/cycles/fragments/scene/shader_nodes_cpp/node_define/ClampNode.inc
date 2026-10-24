NODE_DEFINE(ClampNode)
{
  NodeType *type = NodeType::add("clamp", create, NodeType::SHADER);

  static NodeEnum type_enum;
  type_enum.insert("minmax", NODE_CLAMP_MINMAX);
  type_enum.insert("range", NODE_CLAMP_RANGE);
  SOCKET_ENUM(clamp_type, "Type", type_enum, NODE_CLAMP_MINMAX);

  SOCKET_IN_FLOAT(value, "Value", 1.0f);
  SOCKET_IN_FLOAT(min, "Min", 0.0f);
  SOCKET_IN_FLOAT(max, "Max", 1.0f);

  SOCKET_OUT_FLOAT(result, "Result");

  return type;
}
