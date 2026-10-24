void ClampNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_CLAMP,
                    SVMNodeClamp{
                        .clamp_type = clamp_type,
                        .min = compiler.input_float("Min"),
                        .max = compiler.input_float("Max"),
                        .value = compiler.input_float("Value"),
                        .result_offset = compiler.output("Result"),
                    });
}
