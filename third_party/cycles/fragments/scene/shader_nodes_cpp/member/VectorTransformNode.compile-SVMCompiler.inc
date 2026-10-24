void VectorTransformNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_VECTOR_TRANSFORM,
                    SVMNodeVectorTransform{
                        .transform_type = transform_type,
                        .convert_from = convert_from,
                        .convert_to = convert_to,
                        .vector_in = compiler.input_float3("Vector"),
                        .vector_out_offset = compiler.output("Vector"),
                    });
}
