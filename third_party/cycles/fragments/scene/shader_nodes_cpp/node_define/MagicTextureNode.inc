NODE_DEFINE(MagicTextureNode)
{
  NodeType *type = NodeType::add("magic_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(MagicTextureNode);

  SOCKET_INT(depth, "Depth", 2);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);
  SOCKET_IN_FLOAT(scale, "Scale", 5.0f);
  SOCKET_IN_FLOAT(distortion, "Distortion", 1.0f);

  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_FLOAT(fac, "Fac");

  return type;
}
