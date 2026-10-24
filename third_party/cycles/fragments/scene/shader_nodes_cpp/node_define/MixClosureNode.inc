NODE_DEFINE(MixClosureNode)
{
  NodeType *type = NodeType::add("mix_closure", create, NodeType::SHADER);

  SOCKET_IN_FLOAT(fac, "Fac", 0.5f);
  SOCKET_IN_CLOSURE(closure1, "Closure1");
  SOCKET_IN_CLOSURE(closure2, "Closure2");

  SOCKET_OUT_CLOSURE(closure, "Closure");

  return type;
}
