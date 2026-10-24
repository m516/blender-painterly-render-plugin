void AttributeNode::add_named_attribute_request(AttributeRequestSet *attributes,
                                                const ustring attribute)
{
  attributes->add_standard(attribute);

  /* Request UV if we asked for one of the attributes computed from it.
   * Ideally, this would be handled at a more generic level. */
  const AttributeStandard std = Attribute::name_standard(attribute.c_str());
  if (std == ATTR_STD_UV_TANGENT || std == ATTR_STD_UV_TANGENT_SIGN ||
      std == ATTR_STD_UV_TANGENT_UNDISPLACED || std == ATTR_STD_UV_TANGENT_SIGN_UNDISPLACED)
  {
    attributes->add(ATTR_STD_UV);
  }
  else {
    const char *suffixes[] = {
        ".tangent_sign", ".tangent", ".undisplaced_tangent", ".undisplaced_tangent_sign"};
    for (const char *suffix : suffixes) {
      if (string_endswith(attribute, suffix)) {
        attributes->add(attribute.substr(0, attribute.size() - strlen(suffix)));
      }
    }
  }
}
