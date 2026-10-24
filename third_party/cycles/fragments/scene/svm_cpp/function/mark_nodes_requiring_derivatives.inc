static void mark_nodes_requiring_derivatives(const SVMCompiler &compiler,
                                             ShaderGraph *graph,
                                             const ShaderType type)
{
  if (type == SHADER_TYPE_VOLUME) {
    /* Only support derivatives for surface for now. */
    return;
  }
  queue<ShaderNode *> traverse_queue;
  ShaderNodeSet scheduled;
  /* Check if texture nodes need derivatives. */
  for (ShaderNode *node : graph->nodes) {
    if (node->is_texture_node_and_needs_derivatives(compiler)) {
      traverse_queue.push(node);
      scheduled.insert(node);
    }
  }
  /* Mark all ancestors of texture nodes as requiring derivatives, if the texture nodes themselves
   * need derivatives. */
  while (!traverse_queue.empty()) {
    ShaderNode *node = traverse_queue.front();
    traverse_queue.pop();
    node->set_need_derivatives();
    LOG_DEBUG << "Marking " << node->name << " as requiring derivatives";
    for (ShaderInput *input : node->inputs) {
      if (input->link == nullptr) {
        continue;
      }
      if (scheduled.contains(input->link->parent)) {
        continue;
      }
      traverse_queue.push(input->link->parent);
      scheduled.insert(input->link->parent);
    }
  }
}
