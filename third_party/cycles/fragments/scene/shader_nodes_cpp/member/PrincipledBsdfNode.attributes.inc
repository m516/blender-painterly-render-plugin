void PrincipledBsdfNode::attributes(Shader *shader, AttributeRequestSet *attributes)
{
  if (shader->has_surface_link()) {

    if (!input("Tangent")->link) {
      attributes->add(ATTR_STD_GENERATED);
    }
  }

  ShaderNode::attributes(shader, attributes);
}
