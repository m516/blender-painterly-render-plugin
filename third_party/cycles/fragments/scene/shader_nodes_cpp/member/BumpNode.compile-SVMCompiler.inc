void BumpNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_SET_BUMP,
                    SVMNodeSetBump{.scale = compiler.input_float("Distance"),
                                   .strength = compiler.input_float("Strength"),
                                   .bump_filter_width = filter_width,
                                   .normal_offset = compiler.input_link("Normal"),
                                   .invert = invert,
                                   .use_object_space = use_object_space,
                                   .center_offset = compiler.input_link("SampleCenter"),
                                   .dx_offset = compiler.input_link("SampleX"),
                                   .dy_offset = compiler.input_link("SampleY"),
                                   .out_offset = compiler.output("Normal"),
                                   .bump_state_offset = compiler.get_bump_state_offset()});
}
