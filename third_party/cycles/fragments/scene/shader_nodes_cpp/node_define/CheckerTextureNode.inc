NODE_DEFINE(CheckerTextureNode)
{
  NodeType *type = NodeType::add("checker_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(CheckerTextureNode);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);
  SOCKET_IN_COLOR(color1, "Color1", zero_float3());
  SOCKET_IN_COLOR(color2, "Color2", zero_float3());
  SOCKET_IN_FLOAT(scale, "Scale", 1.0f);

  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_FLOAT(fac, "Fac");

  return type;
}
