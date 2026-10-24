NODE_DEFINE(MixClosureWeightNode)
{
  NodeType *type = NodeType::add("mix_closure_weight", create, NodeType::SHADER);

  SOCKET_IN_FLOAT(weight, "Weight", 1.0f);
  SOCKET_IN_FLOAT(fac, "Fac", 1.0f);

  SOCKET_OUT_FLOAT(weight1, "Weight1");
  SOCKET_OUT_FLOAT(weight2, "Weight2");

  return type;
}
