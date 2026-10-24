void MathNode::expand(ShaderGraph *graph)
{
  if (use_clamp) {
    ShaderOutput *result_out = output("Value");
    if (!result_out->links.empty()) {
      ClampNode *clamp_node = graph->create_node<ClampNode>();
      clamp_node->set_clamp_type(NODE_CLAMP_MINMAX);
      clamp_node->set_min(0.0f);
      clamp_node->set_max(1.0f);
      graph->relink(result_out, clamp_node->output("Result"));
      graph->connect(result_out, clamp_node->input("Value"));
    }
  }
}
