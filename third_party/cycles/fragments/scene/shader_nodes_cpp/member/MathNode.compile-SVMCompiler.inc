void MathNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this,
                    NODE_MATH,
                    SVMNodeMath{
                        .math_type = math_type,
                        .value1 = compiler.input_float("Value1"),
                        .value2 = compiler.input_float("Value2"),
                        .value3 = compiler.input_float("Value3"),
                        .result_offset = compiler.output("Value"),
                    });
}
