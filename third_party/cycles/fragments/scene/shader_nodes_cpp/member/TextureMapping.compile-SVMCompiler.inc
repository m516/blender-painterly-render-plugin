void TextureMapping::compile(SVMCompiler &compiler,
                             const SVMStackOffset offset_in,
                             const SVMStackOffset offset_out,
                             ShaderNode *node)
{
  const Transform tfm = compute_transform();
  compiler.add_node(node,
                    NODE_TEXTURE_MAPPING,
                    SVMNodeTextureMapping{
                        .vec_offset = offset_in,
                        .out_offset = offset_out,
                        .tfm = tfm,
                    });

  if (use_minmax) {
    compiler.add_node(nullptr,
                      NODE_MIN_MAX,
                      SVMNodeMinMax{
                          .vec_offset = offset_out,
                          .out_offset = offset_out,
                          .mn = min,
                          .mx = max,
                      });
  }

  if (type == NORMAL) {
    compiler.add_node(node,
                      NODE_VECTOR_MATH,
                      SVMNodeVectorMath{
                          .math_type = NODE_VECTOR_MATH_NORMALIZE,
                          .a = compiler.input_float3_from_offset(offset_out),
                          .b = {},
                          .c = {},
                          .param1 = {},
                          .value_offset = SVM_STACK_INVALID,
                          .vector_offset = offset_out,
                      });
  }
}
