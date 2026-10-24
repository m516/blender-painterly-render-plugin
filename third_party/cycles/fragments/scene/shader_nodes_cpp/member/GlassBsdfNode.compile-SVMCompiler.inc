void GlassBsdfNode::compile(SVMCompiler &compiler)
{
  closure = distribution;
  BsdfNode::compile(compiler,
                    SVMNodeGlassBsdfData{
                        .color = compiler.input_float3("Color"),
                        .roughness = compiler.input_float("Roughness"),
                        .ior = compiler.input_float("IOR"),
                        .thin_film_thickness = compiler.input_float("Thin Film Thickness"),
                        .thin_film_ior = compiler.input_float("Thin Film IOR"),
                        .normal_offset = compiler.input_link("Normal"),
                    });
}
