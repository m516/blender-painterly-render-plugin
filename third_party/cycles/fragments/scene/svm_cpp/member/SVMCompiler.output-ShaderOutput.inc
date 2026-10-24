SVMStackOffset SVMCompiler::output(ShaderOutput *shader_output)
{
  return (!shader_output->links.empty()) ? stack_assign(shader_output) : SVM_STACK_INVALID;
}
