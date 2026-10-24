bool PrincipledBsdfNode::is_thin_wall()
{
  return (input("Thin Wall")->link == nullptr) && thin_wall;
}
