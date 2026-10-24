void BackgroundNode::constant_fold(const ConstantFolder &folder)
{

  if ((!input("Color")->link && color == zero_float3()) ||
      (!input("Strength")->link && strength == 0.0f))
  {
    folder.discard();
  }
}
