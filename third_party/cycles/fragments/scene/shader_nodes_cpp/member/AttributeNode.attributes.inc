void AttributeNode::attributes(Shader *shader, AttributeRequestSet *attributes)
{

  if (!output("Color")->links.empty() || !output("Vector")->links.empty() ||
      !output("Fac")->links.empty() || !output("Alpha")->links.empty())
  {
    add_named_attribute_request(attributes, attribute);
  }

  if (shader->has_volume) {
    attributes->add(ATTR_STD_GENERATED_TRANSFORM);
  }

  ShaderNode::attributes(shader, attributes);
}
