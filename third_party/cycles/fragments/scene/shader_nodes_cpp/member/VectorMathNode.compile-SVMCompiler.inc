void VectorMathNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_VECTOR_MATH,
                    SVMNodeVectorMath{
                        .math_type = math_type,
                        .a = compiler.input_float3("Vector1"),
                        .b = compiler.input_float3("Vector2"),
                        .c = compiler.input_float3("Vector3"),
                        .param1 = compiler.input_float("Scale"),
                        .value_offset = compiler.output("Value"),
                        .vector_offset = compiler.output("Vector"),
                    });
}
