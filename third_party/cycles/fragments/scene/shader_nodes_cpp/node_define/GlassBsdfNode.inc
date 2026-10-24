NODE_DEFINE(GlassBsdfNode)
{
  NodeType *type = NodeType::add("glass_bsdf", create, NodeType::SHADER);

  SOCKET_IN_COLOR(color, "Color", make_float3(0.8f, 0.8f, 0.8f));
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3(), SocketType::LINK_NORMAL);
  SOCKET_IN_FLOAT(surface_mix_weight, "SurfaceMixWeight", 0.0f, SocketType::SVM_INTERNAL);

  static NodeEnum distribution_enum;
  distribution_enum.insert("beckmann", CLOSURE_BSDF_MICROFACET_BECKMANN_GLASS_ID);
  distribution_enum.insert("ggx", CLOSURE_BSDF_MICROFACET_GGX_GLASS_ID);
  distribution_enum.insert("multi_ggx", CLOSURE_BSDF_MICROFACET_MULTI_GGX_GLASS_ID);
  SOCKET_ENUM(
      distribution, "Distribution", distribution_enum, CLOSURE_BSDF_MICROFACET_GGX_GLASS_ID);
  SOCKET_IN_FLOAT(roughness, "Roughness", 0.0f);
  SOCKET_IN_FLOAT(IOR, "IOR", 1.5f);

  SOCKET_IN_FLOAT(thin_film_thickness, "Thin Film Thickness", 0.0f);
  SOCKET_IN_FLOAT(thin_film_ior, "Thin Film IOR", 1.33f);

  SOCKET_OUT_CLOSURE(BSDF, "BSDF");

  return type;
}
