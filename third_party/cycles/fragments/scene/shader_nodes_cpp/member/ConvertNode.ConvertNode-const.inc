ConvertNode::ConvertNode(const ConvertNode &other)
    : ShaderNode(other),
      from(other.from),
      to(other.to),
      value_color(other.value_color),
      value_string(other.value_string)
{
}
