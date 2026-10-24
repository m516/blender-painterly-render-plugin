NODE_DEFINE(WhiteNoiseTextureNode)
{
  NodeType *type = NodeType::add("white_noise_texture", create, NodeType::SHADER);

  static NodeEnum dimensions_enum;
  dimensions_enum.insert("1D", 1);
  dimensions_enum.insert("2D", 2);
  dimensions_enum.insert("3D", 3);
  dimensions_enum.insert("4D", 4);
  SOCKET_ENUM(dimensions, "Dimensions", dimensions_enum, 3);

  SOCKET_IN_POINT(vector, "Vector", zero_float3());
  SOCKET_IN_FLOAT(w, "W", 0.0f);

  SOCKET_OUT_FLOAT(value, "Value");
  SOCKET_OUT_COLOR(color, "Color");

  return type;
}
