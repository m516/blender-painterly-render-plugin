void TextureCoordinateNode::attributes(Shader *shader, AttributeRequestSet *attributes)
{
  if (shader->has_surface_link()) {
    if (!from_dupli) {
      if (!output("Generated")->links.empty()) {
        attributes->add(ATTR_STD_GENERATED);
      }
      if (!output("UV")->links.empty()) {
        attributes->add(ATTR_STD_UV);
      }
    }
  }

  if (shader->has_volume) {
    if (!from_dupli) {
      if (!output("Generated")->links.empty()) {
        attributes->add(ATTR_STD_GENERATED_TRANSFORM);
      }
    }
  }

  ShaderNode::attributes(shader, attributes);
}
