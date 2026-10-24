unique_ptr<Node> ConvertNode::create(const NodeType *type)
{
  return make_unique<ConvertNode>(type->inputs[0].type, type->outputs[0].type);
}
