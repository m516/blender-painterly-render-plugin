bool PrincipledBsdfNode::has_bssrdf_bump()
{
  return has_surface_bssrdf() && has_bump();
}
