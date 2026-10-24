bool MathNode::is_linear_operation()
{
  switch (math_type) {
    case NODE_MATH_ADD:
    case NODE_MATH_SUBTRACT:
    case NODE_MATH_MULTIPLY:
    case NODE_MATH_MULTIPLY_ADD:
      break;
    case NODE_MATH_DIVIDE:
      return input("Value2")->link == nullptr;
    default:
      return false;
  }

  int num_variable_inputs = 0;
  for (ShaderInput *input : inputs) {
    num_variable_inputs += (input->link) ? 1 : 0;
  }
  return num_variable_inputs <= 1;
}
