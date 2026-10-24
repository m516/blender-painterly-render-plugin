NODE_DEFINE(AddClosureNode)
{
  NodeType *type = NodeType::add("add_closure", create, NodeType::SHADER);

  SOCKET_IN_CLOSURE(closure1, "Closure1");
  SOCKET_IN_CLOSURE(closure2, "Closure2");
  SOCKET_OUT_CLOSURE(closure, "Closure");

  return type;
}
