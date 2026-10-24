void ClampNode::constant_fold(const ConstantFolder &folder)
{
  if (folder.all_inputs_constant()) {
    if (clamp_type == NODE_CLAMP_RANGE && (min > max)) {
      folder.make_constant(clamp(value, max, min));
    }
    else {
      folder.make_constant(clamp(value, min, max));
    }
  }
}
