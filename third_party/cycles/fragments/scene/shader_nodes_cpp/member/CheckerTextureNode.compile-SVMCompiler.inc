void CheckerTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_offset = tex_mapping.compile_begin(compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_CHECKER,
                    SVMNodeTexChecker{
                        .color1 = compiler.input_float3("Color1"),
                        .color2 = compiler.input_float3("Color2"),
                        .scale = compiler.input_float("Scale"),
                        .co = vector_offset,
                        .color_offset = compiler.output("Color"),
                        .fac_offset = compiler.output("Fac"),
                    });

  tex_mapping.compile_end(compiler, vector_in, vector_offset);
}
