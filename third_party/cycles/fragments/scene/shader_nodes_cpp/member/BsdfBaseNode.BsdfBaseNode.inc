BsdfBaseNode::BsdfBaseNode(const NodeType *node_type) : ShaderNode(node_type)
{
  special_type = SHADER_SPECIAL_TYPE_CLOSURE;
}
