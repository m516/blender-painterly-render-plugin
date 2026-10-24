bool ConvertNode::register_on_init = NodeType::register_on_init([] {
  ConvertNode::get_node_types();
  return static_cast<const NodeType *>(nullptr);
});
