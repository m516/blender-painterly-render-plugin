SVMInputFloat3 SVMCompiler::input_float3(const char *name)
{
  ShaderInput *input = current_node->input(name);
  if (input->link) {
    return SVMInputFloat3{
        SVMInputFloat{SVM_INPUT_STACK_OFFSET_MASK | uint(stack_assign(input))}, {0}, {0}};
  }
  float3 default_value = input->parent->get_float3(input->socket_type);
  /* Filter out NaN that would collide with SVM_INPUT_STACK_OFFSET_MASK. */
  if (!isfinite_safe(default_value)) {
    default_value = zero_float3();
  }
  return SVMInputFloat3{
      {__float_as_uint(default_value.x)},
      {__float_as_uint(default_value.y)},
      {__float_as_uint(default_value.z)},
  };
}
