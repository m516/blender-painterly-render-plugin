void SVMCompiler::add_value_node(ShaderNode *shader_node,
                                 const float3 &value,
                                 const int stack_offset)
{
  add_node(shader_node,
           NODE_VALUE_V,
           SVMNodeValueV{
               .out_offset = (SVMStackOffset)stack_offset,
               .value = value,
           });
}
