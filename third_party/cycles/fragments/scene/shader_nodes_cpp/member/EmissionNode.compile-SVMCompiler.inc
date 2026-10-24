void EmissionNode::compile(SVMCompiler &compiler)
{
  ShaderInput *color_in = input("Color");
  ShaderInput *strength_in = input("Strength");

  if (color_in->link || strength_in->link) {
    compiler.add_node(this,
                      NODE_EMISSION_WEIGHT,
                      SVMNodeEmissionWeight{
                          .color = compiler.input_float3("Color"),
                          .strength = compiler.input_float("Strength"),
                      });
  }
  else {
    const float3 w = color * strength;
    compiler.add_node(this,
                      NODE_CLOSURE_SET_WEIGHT,
                      SVMNodeClosureSetWeight{
                          .rgb = w,
                      });
  }

  compiler.add_node(this,
                    NODE_CLOSURE_EMISSION,
                    SVMNodeClosureEmission{
                        .mix_weight_offset = compiler.closure_mix_weight_offset(),
                    });
}
