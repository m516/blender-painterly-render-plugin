bool PrincipledBsdfNode::has_surface_transparent()
{
  if (input("Alpha")->link != nullptr || alpha < (1.0f - CLOSURE_WEIGHT_CUTOFF)) {
    return true;
  }

  /* Smooth thin glass are treated as transparent for non-camera rays. */
  if ((input("Thin Wall")->link || thin_wall) && has_nonzero_weight("Transmission Weight")) {
    if (input("Roughness")->link || input("IOR")->link) {
      return true;
    }

    const float transmission_roughness = bsdf_thin_glass_transmission_roughness(sqr(roughness),
                                                                                ior);
    return roughness_is_almost_specular(transmission_roughness, transmission_roughness);
  }

  return false;
}
