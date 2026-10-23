/* Main Interpreter Loop */
template<uint node_feature_mask, ShaderType type, typename ConstIntegratorGenericState>
ccl_device void svm_eval_nodes(KernelGlobals kg,
                               ConstIntegratorGenericState state,
                               ccl_private ShaderData *sd,
                               ccl_global float *render_buffer,
                               const PathRayVisibility path_visibility,
                               const uint32_t path_flag)
{
  float stack[SVM_STACK_SIZE];
  /* Initialize to silence (false positive?) warning about uninitialized use on Windows. */
  Spectrum closure_weight = zero_spectrum();
  int offset = (sd->shader & SHADER_MASK) * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint));

  while (true) {
    const uint node_type = kernel_data_fetch(svm_nodes, offset++);

    switch (node_type) {
