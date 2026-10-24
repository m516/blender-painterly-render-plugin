void TextureCoordinateNode::compile(OSLCompiler &compiler)
{
  if (bump == SHADER_BUMP_DX) {
    compiler.parameter("bump_offset", "dx");
  }
  else if (bump == SHADER_BUMP_DY) {
    compiler.parameter("bump_offset", "dy");
  }
  else {
    compiler.parameter("bump_offset", "center");
  }
  compiler.parameter("bump_filter_width", bump_filter_width);

  if (compiler.background) {
    compiler.parameter("is_background", true);
  }
  if (compiler.output_type() == SHADER_TYPE_VOLUME) {
    compiler.parameter("is_volume", true);
  }
  compiler.parameter(this, "use_transform");
  const Transform ob_itfm = transform_inverse(ob_tfm);
  compiler.parameter("object_itfm", ob_itfm);

  compiler.parameter(this, "from_dupli");

  compiler.add(this, "node_texture_coordinate");
}
