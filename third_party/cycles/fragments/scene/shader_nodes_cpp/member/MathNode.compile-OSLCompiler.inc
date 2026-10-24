void MathNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "math_type");
  compiler.add(this, "node_math");
}
