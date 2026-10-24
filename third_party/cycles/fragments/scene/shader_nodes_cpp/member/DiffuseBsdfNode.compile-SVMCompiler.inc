void DiffuseBsdfNode::compile(SVMCompiler &compiler)
{
  BsdfNode::compile(compiler,
                    SVMNodeDiffuseBsdfData{.color = compiler.input_float3("Color"),
                                           .roughness = compiler.input_float("Roughness"),
                                           .normal_offset = compiler.input_link("Normal")});
}
