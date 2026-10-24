void VoronoiTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_stack_offset = tex_mapping.compile_begin(
      compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_VORONOI,
                    SVMNodeTexVoronoi{
                        .dimensions = uint(dimensions),
                        .feature = feature,
                        .metric = metric,
                        .w = compiler.input_float("W"),
                        .scale = compiler.input_float("Scale"),
                        .detail = compiler.input_float("Detail"),
                        .roughness = compiler.input_float("Roughness"),
                        .lacunarity = compiler.input_float("Lacunarity"),
                        .smoothness = compiler.input_float("Smoothness"),
                        .exponent = compiler.input_float("Exponent"),
                        .randomness = compiler.input_float("Randomness"),
                        .normalize = use_normalize,
                        .coord = vector_stack_offset,
                        .distance_offset = compiler.output("Distance"),
                        .color_offset = compiler.output("Color"),
                        .position_offset = compiler.output("Position"),
                        .w_out_offset = compiler.output("W"),
                        .radius_offset = compiler.output("Radius"),
                    });
  tex_mapping.compile_end(compiler, vector_in, vector_stack_offset);
}
