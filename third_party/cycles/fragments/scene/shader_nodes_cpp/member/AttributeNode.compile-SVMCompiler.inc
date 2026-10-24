void AttributeNode::compile(SVMCompiler &compiler)
{
  const NodeBumpOffset bump_offset = shader_bump_to_node_bump_offset(bump);
  const bool use_derivative = need_derivatives() || (bump != SHADER_BUMP_NONE);
  const bool store_derivatives = need_derivatives();
  ShaderOutput *color_out = output("Color");
  ShaderOutput *vector_out = output("Vector");
  ShaderOutput *fac_out = output("Fac");
  ShaderOutput *alpha_out = output("Alpha");
  const int attr = compiler.attribute_standard(attribute);
  const float bump_filter_or_stochastic = (compiler.output_type() == SHADER_TYPE_VOLUME) ?
                                              __uint_as_float(uint(stochastic_sample)) :
                                              bump_filter_width;

  if (!color_out->links.empty() || !vector_out->links.empty()) {
    if (!color_out->links.empty()) {
      compiler.add_node(this,
                        NODE_ATTR,
                        SVMNodeAttr{
                            .attr = attr,
                            .out_offset = compiler.output("Color"),
                            .output_type = NODE_ATTR_OUTPUT_FLOAT3,
                            .bump_offset = bump_offset,
                            .store_derivatives = store_derivatives,
                            .bump_filter_width = bump_filter_or_stochastic,
                        },
                        use_derivative);
    }
    if (!vector_out->links.empty()) {
      compiler.add_node(this,
                        NODE_ATTR,
                        SVMNodeAttr{
                            .attr = attr,
                            .out_offset = compiler.output("Vector"),
                            .output_type = NODE_ATTR_OUTPUT_FLOAT3,
                            .bump_offset = bump_offset,
                            .store_derivatives = store_derivatives,
                            .bump_filter_width = bump_filter_or_stochastic,
                        },
                        use_derivative);
    }
  }

  if (!fac_out->links.empty()) {
    compiler.add_node(this,
                      NODE_ATTR,
                      SVMNodeAttr{
                          .attr = attr,
                          .out_offset = compiler.output("Fac"),
                          .output_type = NODE_ATTR_OUTPUT_FLOAT,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .bump_filter_width = bump_filter_or_stochastic,
                      },
                      use_derivative);
  }

  if (!alpha_out->links.empty()) {
    compiler.add_node(this,
                      NODE_ATTR,
                      SVMNodeAttr{
                          .attr = attr,
                          .out_offset = compiler.output("Alpha"),
                          .output_type = NODE_ATTR_OUTPUT_FLOAT_ALPHA,
                          .bump_offset = bump_offset,
                          .store_derivatives = store_derivatives,
                          .bump_filter_width = bump_filter_or_stochastic,
                      },
                      use_derivative);
  }
}
