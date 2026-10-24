template<typename T> void BsdfNode::compile(SVMCompiler &compiler, const T &data)
{
  ShaderInput *color_in = input("Color");

  if (color_in->link) {
    compiler.add_node(this,
                      NODE_CLOSURE_WEIGHT,
                      SVMNodeClosureWeight{
                          .weight_offset = compiler.input_link("Color"),
                      });
  }
  else {
    compiler.add_node(this,
                      NODE_CLOSURE_SET_WEIGHT,
                      SVMNodeClosureSetWeight{
                          .rgb = color,
                      });
  }

  compiler.add_bsdf_node(
      SVMNodeClosureBsdf{
          .closure_type = closure,
          .mix_weight_offset = compiler.closure_mix_weight_offset(),
      },
      data);
}
