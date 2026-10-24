NODE_DEFINE(RefractionBsdfNode)
{
  NodeType *type = NodeType::add("refraction_bsdf", create, NodeType::SHADER);

  SOCKET_IN_COLOR(color, "Color", make_float3(0.8f, 0.8f, 0.8f));
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3(), SocketType::LINK_NORMAL);
  SOCKET_IN_FLOAT(surface_mix_weight, "SurfaceMixWeight", 0.0f, SocketType::SVM_INTERNAL);

  static NodeEnum distribution_enum;
  distribution_enum.insert("beckmann", CLOSURE_BSDF_MICROFACET_BECKMANN_REFRACTION_ID);
  distribution_enum.insert("ggx", CLOSURE_BSDF_MICROFACET_GGX_REFRACTION_ID);
  SOCKET_ENUM(
      distribution, "Distribution", distribution_enum, CLOSURE_BSDF_MICROFACET_GGX_REFRACTION_ID);

  SOCKET_IN_FLOAT(roughness, "Roughness", 0.0f);
  SOCKET_IN_FLOAT(IOR, "IOR", 0.3f);

  SOCKET_OUT_CLOSURE(BSDF, "BSDF");

  return type;
}
