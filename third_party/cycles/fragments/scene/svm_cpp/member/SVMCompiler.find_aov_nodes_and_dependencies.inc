void SVMCompiler::find_aov_nodes_and_dependencies(ShaderNodeSet &aov_nodes,
                                                  ShaderGraph *graph,
                                                  CompilerState *state)
{
  for (ShaderNode *node : graph->nodes) {
    if (node->special_type == SHADER_SPECIAL_TYPE_OUTPUT_AOV) {
      OutputAOVNode *aov_node = static_cast<OutputAOVNode *>(node);
      if (aov_node->offset >= 0) {
        aov_nodes.insert(aov_node);
        for (ShaderInput *in : node->inputs) {
          if (in->link != nullptr) {
            find_dependencies(aov_nodes, state->nodes_done, in);
          }
        }
      }
    }
  }
}
