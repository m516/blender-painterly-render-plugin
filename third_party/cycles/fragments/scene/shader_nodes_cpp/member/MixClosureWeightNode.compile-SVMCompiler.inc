void MixClosureWeightNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_MIX_CLOSURE,
                    SVMNodeMixClosure{
                        .fac = compiler.input_float("Fac"),
                        .in_weight_offset = compiler.input_link("Weight"),
                        .weight1_offset = compiler.output("Weight1"),
                        .weight2_offset = compiler.output("Weight2"),
                    });
}
