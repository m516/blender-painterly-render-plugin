SVMInputFloat3 SVMCompiler::input_float3_from_offset(const SVMStackOffset offset)
{
  return SVMInputFloat3{SVMInputFloat{SVM_INPUT_STACK_OFFSET_MASK | uint(offset)}, {0}, {0}};
}
