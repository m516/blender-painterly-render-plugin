void GradientTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_offset = tex_mapping.compile_begin(compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_GRADIENT,
                    SVMNodeTexGradient{
                        .gradient_type = gradient_type,
                        .co = vector_offset,
                        .fac_offset = compiler.output("Fac"),
                        .color_offset = compiler.output("Color"),
                    });

  tex_mapping.compile_end(compiler, vector_in, vector_offset);
}
