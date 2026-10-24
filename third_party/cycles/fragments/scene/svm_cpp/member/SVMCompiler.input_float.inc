SVMInputFloat SVMCompiler::input_float(const char *name)
{
  ShaderInput *input = current_node->input(name);
  if (input->link) {
    return SVMInputFloat{SVM_INPUT_STACK_OFFSET_MASK | uint(stack_assign(input))};
  }
  float default_value = input->parent->get_float(input->socket_type);
  /* Filter out NaN that would collide with SVM_INPUT_STACK_OFFSET_MASK. */
  if (!isfinite_safe(default_value)) {
    default_value = 0.0f;
  }
  return SVMInputFloat{__float_as_uint(default_value)};
}
