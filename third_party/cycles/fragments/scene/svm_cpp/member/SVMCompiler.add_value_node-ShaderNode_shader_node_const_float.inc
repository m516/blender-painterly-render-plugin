void SVMCompiler::add_value_node(ShaderNode *shader_node,
                                 const float value,
                                 const int stack_offset)
{
  add_node(shader_node,
           NODE_VALUE_F,
           SVMNodeValueF{
               .value = value,
               .out_offset = (SVMStackOffset)stack_offset,
           });
}
