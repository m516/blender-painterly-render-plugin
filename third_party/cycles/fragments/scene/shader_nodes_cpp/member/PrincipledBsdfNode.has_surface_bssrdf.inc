bool PrincipledBsdfNode::has_surface_bssrdf()
{
  if (is_thin_wall()) {
    /* Subsurface in thin-walled mode is approximated via diffuse lobes, it doesn't contain real
     * subsurface. */
    return false;
  }

  return subsurface_has_positive_weight();
}
