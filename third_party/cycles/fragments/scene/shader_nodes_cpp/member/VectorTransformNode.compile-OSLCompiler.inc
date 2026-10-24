void VectorTransformNode::compile(OSLCompiler &compiler)
{
  compiler.parameter(this, "transform_type");
  compiler.parameter(this, "convert_from");
  compiler.parameter(this, "convert_to");
  compiler.add(this, "node_vector_transform");
}
