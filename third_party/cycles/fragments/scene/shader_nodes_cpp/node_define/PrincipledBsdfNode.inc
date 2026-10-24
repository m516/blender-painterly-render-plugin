NODE_DEFINE(PrincipledBsdfNode)
{
  NodeType *type = NodeType::add("principled_bsdf", create, NodeType::SHADER);

  static NodeEnum distribution_enum;
  distribution_enum.insert("ggx", CLOSURE_BSDF_MICROFACET_GGX_GLASS_ID);
  distribution_enum.insert("multi_ggx", CLOSURE_BSDF_MICROFACET_MULTI_GGX_GLASS_ID);
  SOCKET_ENUM(
      distribution, "Distribution", distribution_enum, CLOSURE_BSDF_MICROFACET_MULTI_GGX_GLASS_ID);

  static NodeEnum subsurface_method_enum;
  subsurface_method_enum.insert("burley", CLOSURE_BSSRDF_BURLEY_ID);
  subsurface_method_enum.insert("random_walk", CLOSURE_BSSRDF_RANDOM_WALK_ID);
  subsurface_method_enum.insert("random_walk_skin", CLOSURE_BSSRDF_RANDOM_WALK_SKIN_ID);
  subsurface_method_enum.insert("random_walk_legacy", CLOSURE_BSSRDF_RANDOM_WALK_LEGACY_ID);
  SOCKET_ENUM(subsurface_method,
              "Subsurface Method",
              subsurface_method_enum,
              CLOSURE_BSSRDF_RANDOM_WALK_ID);

  SOCKET_IN_COLOR(base_color, "Base Color", make_float3(0.8f, 0.8f, 0.8f))
  SOCKET_IN_FLOAT(metallic, "Metallic", 0.0f);
  SOCKET_IN_FLOAT(roughness, "Roughness", 0.5f);
  SOCKET_IN_FLOAT(ior, "IOR", 1.5f);
  SOCKET_IN_FLOAT(alpha, "Alpha", 1.0f);
  /* FIXME: `SOCKET_IN_BOOLEAN()` doesn't pass the value correctly, need investigation. */
  SOCKET_IN_INT(thin_wall, "Thin Wall", int(false));
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3(), SocketType::LINK_NORMAL);

  SOCKET_IN_FLOAT(diffuse_roughness, "Diffuse Roughness", 0.0f);

  SOCKET_IN_FLOAT(subsurface_weight, "Subsurface Weight", 0.0f);
  SOCKET_IN_FLOAT(subsurface_scale, "Subsurface Scale", 0.005f);
  SOCKET_IN_VECTOR(subsurface_radius, "Subsurface Radius", make_float3(1.0f, 0.2f, 0.1f));
  SOCKET_IN_FLOAT(subsurface_ior, "Subsurface IOR", 1.4f);
  SOCKET_IN_FLOAT(subsurface_anisotropy, "Subsurface Anisotropy", 0.0f);

  SOCKET_IN_FLOAT(specular_ior_level, "Specular IOR Level", 0.5f);
  SOCKET_IN_COLOR(specular_tint, "Specular Tint", one_float3());
  SOCKET_IN_FLOAT(anisotropic, "Anisotropic", 0.0f);
  SOCKET_IN_FLOAT(anisotropic_rotation, "Anisotropic Rotation", 0.0f);
  SOCKET_IN_NORMAL(tangent, "Tangent", zero_float3(), SocketType::LINK_TANGENT);

  SOCKET_IN_FLOAT(transmission_weight, "Transmission Weight", 0.0f);

  SOCKET_IN_FLOAT(sheen_weight, "Sheen Weight", 0.0f);
  SOCKET_IN_FLOAT(sheen_roughness, "Sheen Roughness", 0.5f);
  SOCKET_IN_COLOR(sheen_tint, "Sheen Tint", one_float3());

  SOCKET_IN_FLOAT(coat_weight, "Coat Weight", 0.0f);
  SOCKET_IN_FLOAT(coat_roughness, "Coat Roughness", 0.03f);
  SOCKET_IN_FLOAT(coat_ior, "Coat IOR", 1.5f);
  SOCKET_IN_COLOR(coat_tint, "Coat Tint", one_float3());
  SOCKET_IN_NORMAL(coat_normal, "Coat Normal", zero_float3(), SocketType::LINK_NORMAL);

  SOCKET_IN_COLOR(emission_color, "Emission Color", one_float3());
  SOCKET_IN_FLOAT(emission_strength, "Emission Strength", 0.0f);

  SOCKET_IN_FLOAT(thin_film_thickness, "Thin Film Thickness", 0.0f);
  SOCKET_IN_FLOAT(thin_film_ior, "Thin Film IOR", 1.33f);

  SOCKET_IN_FLOAT(surface_mix_weight, "SurfaceMixWeight", 0.0f, SocketType::SVM_INTERNAL);

  SOCKET_OUT_CLOSURE(BSDF, "BSDF");

  return type;
}
