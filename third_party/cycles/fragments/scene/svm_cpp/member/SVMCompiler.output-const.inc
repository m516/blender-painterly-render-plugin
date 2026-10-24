SVMStackOffset SVMCompiler::output(const char *name)
{
  ShaderOutput *shader_output = current_node->output(name);
  return output(shader_output);
}
