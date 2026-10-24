void RefractionBsdfNode::compile(SVMCompiler &compiler)
{
  closure = distribution;
  BsdfNode::compile(compiler,
                    SVMNodeRefractionBsdfData{
                        .roughness = compiler.input_float("Roughness"),
                        .ior = compiler.input_float("IOR"),
                        .normal_offset = compiler.input_link("Normal"),
                    });
}
