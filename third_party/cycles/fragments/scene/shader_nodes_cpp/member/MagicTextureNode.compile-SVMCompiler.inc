void MagicTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_offset = tex_mapping.compile_begin(compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_MAGIC,
                    SVMNodeTexMagic{
                        .scale = compiler.input_float("Scale"),
                        .distortion = compiler.input_float("Distortion"),
                        .depth = uint8_t(depth),
                        .co = vector_offset,
                        .color_offset = compiler.output("Color"),
                        .fac_offset = compiler.output("Fac"),
                    });

  tex_mapping.compile_end(compiler, vector_in, vector_offset);
}
