bool PrincipledBsdfNode::has_nonzero_weight(const char *name)
{
  ShaderInput *weight_in = input(name);
  if (weight_in == nullptr) {
    return true;
  }
  if (weight_in->link != nullptr) {
    return true;
  }
  return (get_float(weight_in->socket_type) >= CLOSURE_WEIGHT_CUTOFF);
}
