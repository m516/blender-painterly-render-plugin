void OutputNode::compile(SVMCompiler &compiler)
{
  if (compiler.output_type() == SHADER_TYPE_DISPLACEMENT) {
    ShaderInput *displacement_in = input("Displacement");

    if (displacement_in->link) {
      compiler.add_node(this,
                        NODE_SET_DISPLACEMENT,
                        SVMNodeSetDisplacement{.fac_offset = compiler.input_link("Displacement")});
    }
  }
}
