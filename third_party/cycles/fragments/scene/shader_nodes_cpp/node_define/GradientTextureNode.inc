NODE_DEFINE(GradientTextureNode)
{
  NodeType *type = NodeType::add("gradient_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(GradientTextureNode);

  static NodeEnum type_enum;
  type_enum.insert("linear", NODE_BLEND_LINEAR);
  type_enum.insert("quadratic", NODE_BLEND_QUADRATIC);
  type_enum.insert("easing", NODE_BLEND_EASING);
  type_enum.insert("diagonal", NODE_BLEND_DIAGONAL);
  type_enum.insert("radial", NODE_BLEND_RADIAL);
  type_enum.insert("quadratic_sphere", NODE_BLEND_QUADRATIC_SPHERE);
  type_enum.insert("spherical", NODE_BLEND_SPHERICAL);
  SOCKET_ENUM(gradient_type, "Type", type_enum, NODE_BLEND_LINEAR);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);

  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_FLOAT(fac, "Fac");

  return type;
}
