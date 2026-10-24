void NoiseTextureNode::compile(SVMCompiler &compiler)
{
  ShaderInput *vector_in = input("Vector");

  const SVMStackOffset vector_stack_offset = tex_mapping.compile_begin(
      compiler, vector_in, nullptr);
  compiler.add_node(this,
                    NODE_TEX_NOISE,
                    SVMNodeTexNoise{
                        .dimensions = uint(dimensions),
                        .noise_type = type,
                        .normalize = uint(use_normalize),
                        .w = compiler.input_float("W"),
                        .scale = compiler.input_float("Scale"),
                        .detail = compiler.input_float("Detail"),
                        .roughness = compiler.input_float("Roughness"),
                        .lacunarity = compiler.input_float("Lacunarity"),
                        .offset = compiler.input_float("Offset"),
                        .gain = compiler.input_float("Gain"),
                        .distortion = compiler.input_float("Distortion"),
                        .vector = vector_stack_offset,
                        .value_offset = compiler.output("Fac"),
                        .color_offset = compiler.output("Color"),
                    });

  tex_mapping.compile_end(compiler, vector_in, vector_stack_offset);
}
