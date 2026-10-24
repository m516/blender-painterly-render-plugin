bool GlossyBsdfNode::is_isotropic()
{
  /* Keep in sync with the thresholds in OSL's node_glossy_bsdf and SVM's svm_node_closure_bsdf.
   */
  return (!input("Anisotropy")->link && fabsf(anisotropy) <= 1e-4f);
}
