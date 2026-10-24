void ColorNode::constant_fold(const ConstantFolder &folder)
{
  folder.make_constant(value);
}
