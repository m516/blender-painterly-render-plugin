void GlossyBsdfNode::compile(SVMCompiler &compiler)
{
  closure = distribution;

  /* TODO: Just use weight for legacy MultiGGX? Would also simplify OSL. */
  BsdfNode::compile(compiler,
                    SVMNodeGlossyBsdfData{
                        .color = (closure == CLOSURE_BSDF_MICROFACET_MULTI_GGX_ID) ?
                                     compiler.input_float3("Color") :
                                     SVMInputFloat3{},
                        .roughness = compiler.input_float("Roughness"),
                        .anisotropy = compiler.input_float("Anisotropy"),
                        .rotation = compiler.input_float("Rotation"),
                        .normal_offset = compiler.input_link("Normal"),
                        .tangent_offset = compiler.input_link("Tangent"),
                    });
}
