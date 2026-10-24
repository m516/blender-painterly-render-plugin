void AddClosureNode::constant_fold(const ConstantFolder &folder)
{
  ShaderInput *closure1_in = input("Closure1");
  ShaderInput *closure2_in = input("Closure2");

  /* remove useless add closures nodes */
  if (!closure1_in->link) {
    folder.bypass_or_discard(closure2_in);
  }
  else if (!closure2_in->link) {
    folder.bypass_or_discard(closure1_in);
  }
}
