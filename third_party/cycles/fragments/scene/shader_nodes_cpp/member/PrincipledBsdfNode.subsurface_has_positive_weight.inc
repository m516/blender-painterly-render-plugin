bool PrincipledBsdfNode::subsurface_has_positive_weight()
{
  return (input("Subsurface Weight")->link != nullptr ||
          subsurface_weight > CLOSURE_WEIGHT_CUTOFF) &&
         (input("Subsurface Scale")->link != nullptr || subsurface_scale != 0.0f);
}
