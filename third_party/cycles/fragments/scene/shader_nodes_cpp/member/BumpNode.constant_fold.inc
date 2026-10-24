void BumpNode::constant_fold(const ConstantFolder &folder)
{
  ShaderInput *normal_in = input("Normal");

  if (input("Height")->link == nullptr) {
    if (normal_in->link == nullptr) {
      GeometryNode *geom = folder.graph->create_node<GeometryNode>();
      folder.bypass(geom->output("Normal"));
    }
    else {
      folder.bypass(normal_in->link);
    }
  }

  /* TODO(sergey): Ignore bump with zero strength. */
}
