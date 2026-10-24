GlassBsdfNode::GlassBsdfNode() : BsdfNode(get_node_type())
{
  closure = CLOSURE_BSDF_MICROFACET_GGX_GLASS_ID;
}
