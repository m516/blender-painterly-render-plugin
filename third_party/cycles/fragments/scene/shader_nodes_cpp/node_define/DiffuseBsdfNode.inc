NODE_DEFINE(DiffuseBsdfNode)
{
  NodeType *type = NodeType::add("diffuse_bsdf", create, NodeType::SHADER);

  SOCKET_IN_COLOR(color, "Color", make_float3(0.8f, 0.8f, 0.8f));
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3(), SocketType::LINK_NORMAL);
  SOCKET_IN_FLOAT(surface_mix_weight, "SurfaceMixWeight", 0.0f, SocketType::SVM_INTERNAL);
  SOCKET_IN_FLOAT(roughness, "Roughness", 0.0f);

  SOCKET_OUT_CLOSURE(BSDF, "BSDF");

  return type;
}
