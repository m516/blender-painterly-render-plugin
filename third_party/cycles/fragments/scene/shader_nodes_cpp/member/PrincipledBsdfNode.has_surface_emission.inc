bool PrincipledBsdfNode::has_surface_emission()
{
  return (input("Emission Color")->link != nullptr ||
          reduce_max(emission_color) > CLOSURE_WEIGHT_CUTOFF) &&
         (input("Emission Strength")->link != nullptr ||
          emission_strength > CLOSURE_WEIGHT_CUTOFF);
}
