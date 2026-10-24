void SetNormalNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_CLOSURE_SET_NORMAL,
                    SVMNodeClosureSetNormal{
                        .direction_offset = compiler.input_link("Direction"),
                        .normal_offset = compiler.output("Normal"),
                    });
}
