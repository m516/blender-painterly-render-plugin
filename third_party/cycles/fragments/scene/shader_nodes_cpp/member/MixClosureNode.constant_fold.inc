void MixClosureNode::constant_fold(const ConstantFolder &folder)
{
  ShaderInput *closure1_in = input("Closure1");
  ShaderInput *closure2_in = input("Closure2");

  /* remove useless mix closures nodes */
  if (closure1_in->link == closure2_in->link) {
    folder.bypass_or_discard(closure1_in);
  }
  /* remove unused mix closure input when factor is 0.0 or 1.0
   * check for closure links and make sure factor link is disconnected */
  else if (!input("Fac")->link) {
    /* factor 0.0 */
    if (fac <= 0.0f) {
      folder.bypass_or_discard(closure1_in);
    }
    /* factor 1.0 */
    else if (fac >= 1.0f) {
      folder.bypass_or_discard(closure2_in);
    }
  }
}
