NODE_DEFINE(GlossyBsdfNode)
{
  NodeType *type = NodeType::add("glossy_bsdf", create, NodeType::SHADER);

  SOCKET_IN_COLOR(color, "Color", make_float3(0.8f, 0.8f, 0.8f));
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3(), SocketType::LINK_NORMAL);
  SOCKET_IN_FLOAT(surface_mix_weight, "SurfaceMixWeight", 0.0f, SocketType::SVM_INTERNAL);

  static NodeEnum distribution_enum;
  distribution_enum.insert("beckmann", CLOSURE_BSDF_MICROFACET_BECKMANN_ID);
  distribution_enum.insert("ggx", CLOSURE_BSDF_MICROFACET_GGX_ID);
  distribution_enum.insert("ashikhmin_shirley", CLOSURE_BSDF_ASHIKHMIN_SHIRLEY_ID);
  distribution_enum.insert("multi_ggx", CLOSURE_BSDF_MICROFACET_MULTI_GGX_ID);
  SOCKET_ENUM(distribution, "Distribution", distribution_enum, CLOSURE_BSDF_MICROFACET_GGX_ID);

  SOCKET_IN_VECTOR(tangent, "Tangent", zero_float3(), SocketType::LINK_TANGENT);

  SOCKET_IN_FLOAT(roughness, "Roughness", 0.5f);
  SOCKET_IN_FLOAT(anisotropy, "Anisotropy", 0.0f);
  SOCKET_IN_FLOAT(rotation, "Rotation", 0.0f);

  SOCKET_OUT_CLOSURE(BSDF, "BSDF");

  return type;
}
