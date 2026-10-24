NodeConvert ConvertNode::convert_type()
{
  if (from == SocketType::FLOAT) {
    if (to == SocketType::INT) {
      /* float to int */
      return NODE_CONVERT_FI;
    }
    /* float to float3 */
    return NODE_CONVERT_FV;
  }
  if (from == SocketType::INT) {
    if (to == SocketType::FLOAT) {
      /* int to float */
      return NODE_CONVERT_IF;
    }
    /* int to vector/point/normal */
    return NODE_CONVERT_IV;
  }
  if (to == SocketType::FLOAT) {
    if (from == SocketType::COLOR) {
      /* color to float */
      return NODE_CONVERT_CF;
    }
    /* vector/point/normal to float */
    return NODE_CONVERT_VF;
  }
  if (to == SocketType::INT) {
    if (from == SocketType::COLOR) {
      /* color to int */
      return NODE_CONVERT_CI;
    }
    /* vector/point/normal to int */
    return NODE_CONVERT_VI;
  }
  return NODE_CONVERT_NONE;
}
