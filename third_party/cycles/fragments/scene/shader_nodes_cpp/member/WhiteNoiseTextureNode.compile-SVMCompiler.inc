void WhiteNoiseTextureNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_TEX_WHITE_NOISE,
                    SVMNodeTexWhiteNoise{
                        .dimensions = uint(dimensions),
                        .vector = compiler.input_float3("Vector"),
                        .w = compiler.input_float("W"),
                        .value_offset = compiler.output("Value"),
                        .color_offset = compiler.output("Color"),
                    });
}
