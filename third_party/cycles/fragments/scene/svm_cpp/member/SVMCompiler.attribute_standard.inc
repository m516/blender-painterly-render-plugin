uint SVMCompiler::attribute_standard(ustring name)
{
  const AttributeStandard std = Attribute::name_standard(name.c_str());
  return (std) ? attribute(std) : attribute(name);
}
