GlossyBsdfNode::GlossyBsdfNode() : BsdfNode(get_node_type())
{
  closure = CLOSURE_BSDF_MICROFACET_GGX_ID;
}
