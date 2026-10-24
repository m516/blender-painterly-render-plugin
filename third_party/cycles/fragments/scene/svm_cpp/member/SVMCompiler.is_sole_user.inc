bool SVMCompiler::is_sole_user(const ShaderNode *node,
                               const ShaderOutput *output,
                               const ShaderNodeSet &done)
{
  /* Check if the node is the only remaining user of the output, meaning the
   * output's stack space can be freed once the node is compiled. */

  /* optimization we should add: verify if in->parent is actually used */
  for (const ShaderInput *in : output->links) {
    if (in->parent != node && !done.contains(in->parent)) {
      return false;
    }
  }
  return true;
}
