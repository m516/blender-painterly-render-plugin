bool BsdfBaseNode::has_bump()
{
  /* detect if anything is plugged into the normal input besides the default */
  ShaderInput *normal_in = input("Normal");
  return (normal_in && normal_in->link &&
          normal_in->link->parent->special_type != SHADER_SPECIAL_TYPE_GEOMETRY);
}
