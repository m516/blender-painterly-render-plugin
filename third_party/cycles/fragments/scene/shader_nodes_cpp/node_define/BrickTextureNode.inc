NODE_DEFINE(BrickTextureNode)
{
  NodeType *type = NodeType::add("brick_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(BrickTextureNode);

  SOCKET_FLOAT(offset, "Offset", 0.5f);
  SOCKET_INT(offset_frequency, "Offset Frequency", 2);
  SOCKET_FLOAT(squash, "Squash", 1.0f);
  SOCKET_INT(squash_frequency, "Squash Frequency", 2);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);

  SOCKET_IN_COLOR(color1, "Color1", zero_float3());
  SOCKET_IN_COLOR(color2, "Color2", zero_float3());
  SOCKET_IN_COLOR(mortar, "Mortar", zero_float3());
  SOCKET_IN_FLOAT(scale, "Scale", 5.0f);
  SOCKET_IN_FLOAT(mortar_size, "Mortar Size", 0.02f);
  SOCKET_IN_FLOAT(mortar_smooth, "Mortar Smooth", 0.0f);
  SOCKET_IN_FLOAT(bias, "Bias", 0.0f);
  SOCKET_IN_FLOAT(brick_width, "Brick Width", 0.5f);
  SOCKET_IN_FLOAT(row_height, "Row Height", 0.25f);

  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_FLOAT(fac, "Fac");

  return type;
}
