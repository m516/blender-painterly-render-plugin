NODE_DEFINE(BumpNode)
{
  NodeType *type = NodeType::add("bump", create, NodeType::SHADER);

  SOCKET_BOOLEAN(invert, "Invert", false);
  SOCKET_BOOLEAN(use_object_space, "UseObjectSpace", false);

  /* this input is used by the user, but after graph transform it is no longer
   * used and moved to sampler center/x/y instead */
  SOCKET_IN_FLOAT(height, "Height", 1.0f);

  SOCKET_IN_FLOAT(sample_center, "SampleCenter", 0.0f);
  SOCKET_IN_FLOAT(sample_x, "SampleX", 0.0f);
  SOCKET_IN_FLOAT(sample_y, "SampleY", 0.0f);
  SOCKET_IN_NORMAL(normal, "Normal", zero_float3(), SocketType::LINK_NORMAL);
  SOCKET_IN_FLOAT(strength, "Strength", 1.0f);
  SOCKET_IN_FLOAT(distance, "Distance", 0.1f);
  SOCKET_IN_FLOAT(filter_width, "Filter Width", 0.1f);

  SOCKET_OUT_NORMAL(normal, "Normal");

  return type;
}
