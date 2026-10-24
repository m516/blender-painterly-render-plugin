void WaveTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_offset = tex_mapping.compile_begin(compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_WAVE,
                    SVMNodeTexWave{
                        .wave_type = wave_type,
                        .bands_direction = bands_direction,
                        .rings_direction = rings_direction,
                        .profile = profile,
                        .scale = compiler.input_float("Scale"),
                        .distortion = compiler.input_float("Distortion"),
                        .detail = compiler.input_float("Detail"),
                        .dscale = compiler.input_float("Detail Scale"),
                        .droughness = compiler.input_float("Detail Roughness"),
                        .phase = compiler.input_float("Phase Offset"),
                        .co = vector_offset,
                        .color_offset = compiler.output("Color"),
                        .fac_offset = compiler.output("Fac"),
                    });

  tex_mapping.compile_end(compiler, vector_in, vector_offset);
}
