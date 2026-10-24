void OutputNode::compile(OSLCompiler &compiler)
{
  if (compiler.output_type() == SHADER_TYPE_SURFACE) {
    compiler.add(this, "node_output_surface");
  }
  else if (compiler.output_type() == SHADER_TYPE_VOLUME) {
    compiler.add(this, "node_output_volume");
  }
  else if (compiler.output_type() == SHADER_TYPE_DISPLACEMENT) {
    compiler.add(this, "node_output_displacement");
  }
}
