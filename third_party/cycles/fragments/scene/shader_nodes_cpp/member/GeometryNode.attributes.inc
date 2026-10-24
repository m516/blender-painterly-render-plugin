void GeometryNode::attributes(Shader *shader, AttributeRequestSet *attributes)
{
  if (shader->has_surface_link()) {
    if (!output("Tangent")->links.empty()) {
      attributes->add(ATTR_STD_GENERATED);
    }
    if (!output("Pointiness")->links.empty()) {
      attributes->add(ATTR_STD_POINTINESS);
    }
    if (!output("Random Per Island")->links.empty()) {
      attributes->add(ATTR_STD_RANDOM_PER_ISLAND);
    }
  }

  ShaderNode::attributes(shader, attributes);
}
