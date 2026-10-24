PrincipledBsdfNode::PrincipledBsdfNode() : BsdfBaseNode(get_node_type())
{
  closure = CLOSURE_BSDF_PRINCIPLED_ID;
  distribution = CLOSURE_BSDF_MICROFACET_MULTI_GGX_GLASS_ID;
}
