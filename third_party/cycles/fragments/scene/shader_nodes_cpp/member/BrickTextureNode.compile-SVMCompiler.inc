void BrickTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_offset = tex_mapping.compile_begin(compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_BRICK,
                    SVMNodeTexBrick{
                        .color1 = compiler.input_float3("Color1"),
                        .color2 = compiler.input_float3("Color2"),
                        .mortar = compiler.input_float3("Mortar"),
                        .scale = compiler.input_float("Scale"),
                        .mortar_size = compiler.input_float("Mortar Size"),
                        .bias = compiler.input_float("Bias"),
                        .brick_width = compiler.input_float("Brick Width"),
                        .row_height = compiler.input_float("Row Height"),
                        .mortar_smooth = compiler.input_float("Mortar Smooth"),
                        .offset_amount = offset,
                        .squash_amount = squash,
                        .offset_frequency = uint8_t(offset_frequency),
                        .squash_frequency = uint8_t(squash_frequency),
                        .co = vector_offset,
                        .color_offset = compiler.output("Color"),
                        .fac_offset = compiler.output("Fac"),
                    });

  tex_mapping.compile_end(compiler, vector_in, vector_offset);
}
