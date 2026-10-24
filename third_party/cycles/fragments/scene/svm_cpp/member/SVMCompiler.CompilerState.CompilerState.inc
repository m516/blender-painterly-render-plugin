SVMCompiler::CompilerState::CompilerState(ShaderGraph *graph)
{
  int max_id = 0;
  for (ShaderNode *node : graph->nodes) {
    max_id = max(node->id, max_id);
  }
  nodes_done_flag.resize(max_id + 1, false);
  node_feature_mask = 0;
}
