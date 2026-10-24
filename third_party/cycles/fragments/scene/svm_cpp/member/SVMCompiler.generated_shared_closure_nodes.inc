void SVMCompiler::generated_shared_closure_nodes(ShaderNode *root_node,
                                                 ShaderNode *node,
                                                 CompilerState *state,
                                                 const ShaderNodeSet &shared)
{
  if (shared.contains(node)) {
    generate_multi_closure(root_node, node, state);
  }
  else {
    for (ShaderInput *in : node->inputs) {
      if (in->type() == SocketType::CLOSURE && in->link) {
        generated_shared_closure_nodes(root_node, in->link->parent, state, shared);
      }
    }
  }
}
