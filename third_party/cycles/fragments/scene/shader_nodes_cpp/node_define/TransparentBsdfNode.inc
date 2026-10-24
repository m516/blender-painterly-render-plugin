NODE_DEFINE(TransparentBsdfNode)
{
  NodeType *type = NodeType::add("transparent_bsdf", create, NodeType::SHADER);

  SOCKET_IN_COLOR(color, "Color", one_float3());
  SOCKET_IN_FLOAT(surface_mix_weight, "SurfaceMixWeight", 0.0f, SocketType::SVM_INTERNAL);

  SOCKET_OUT_CLOSURE(BSDF, "BSDF");

  return type;
}
