void ConvertNode::compile(SVMCompiler &compiler)
{
  /* proxy nodes should have been removed at this point */
  assert(special_type != SHADER_SPECIAL_TYPE_PROXY);

  ShaderInput *in = inputs[0];
  ShaderOutput *out = outputs[0];

  const NodeConvert cvt_type = convert_type();
  if (cvt_type != NODE_CONVERT_NONE) {
    compiler.add_node(this,
                      NODE_CONVERT,
                      SVMNodeConvert{
                          .convert_type = cvt_type,
                          .from_offset = compiler.input_link(in->name().c_str()),
                          .to_offset = compiler.output(out->name().c_str()),
                      });
  }
  else {
    /* float3 to float3 */
    if (in->link) {
      /* no op in SVM */
      compiler.stack_link(in, out);
    }
    else {
      /* set 0,0,0 value */
      compiler.add_value_node(this, value_color, compiler.output(out->name().c_str()));
    }
  }
}
