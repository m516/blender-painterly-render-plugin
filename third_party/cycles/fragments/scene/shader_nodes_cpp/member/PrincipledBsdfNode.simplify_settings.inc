void PrincipledBsdfNode::simplify_settings(Scene * /* scene */)
{
  if (!has_surface_emission()) {
    /* Emission will be zero, so optimize away any connected emission input. */
    disconnect_unused_input("Emission Color");
    disconnect_unused_input("Emission Strength");
  }

  if (is_thin_wall()) {
    disconnect_unused_input("Subsurface Radius");
    disconnect_unused_input("Subsurface Scale");
    disconnect_unused_input("Subsurface IOR");
  }
  else if (!has_surface_bssrdf()) {
    disconnect_unused_input("Subsurface Weight");
    disconnect_unused_input("Subsurface Radius");
    disconnect_unused_input("Subsurface Scale");
    disconnect_unused_input("Subsurface IOR");
    disconnect_unused_input("Subsurface Anisotropy");
  }

  if (!has_nonzero_weight("Coat Weight")) {
    disconnect_unused_input("Coat Weight");
    disconnect_unused_input("Coat IOR");
    disconnect_unused_input("Coat Roughness");
    disconnect_unused_input("Coat Tint");
  }

  if (!has_nonzero_weight("Sheen Weight")) {
    disconnect_unused_input("Sheen Weight");
    disconnect_unused_input("Sheen Roughness");
    disconnect_unused_input("Sheen Tint");
  }

  if (!has_nonzero_weight("Anisotropic")) {
    disconnect_unused_input("Anisotropic");
    disconnect_unused_input("Anisotropic Rotation");
    disconnect_unused_input("Tangent");
  }

  if (!has_nonzero_weight("Thin Film Thickness")) {
    disconnect_unused_input("Thin Film Thickness");
    disconnect_unused_input("Thin Film IOR");
  }
}
