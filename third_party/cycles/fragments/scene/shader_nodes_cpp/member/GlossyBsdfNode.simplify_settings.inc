void GlossyBsdfNode::simplify_settings(Scene * /* scene */)
{
  /* If the anisotropy is close enough to zero, fall back to the isotropic case. */
  if (is_isotropic()) {
    disconnect_unused_input("Tangent");
  }
}
