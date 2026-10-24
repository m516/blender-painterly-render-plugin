NODE_DEFINE(VectorMathNode)
{
  NodeType *type = NodeType::add("vector_math", create, NodeType::SHADER);

  static NodeEnum type_enum;
  type_enum.insert("add", NODE_VECTOR_MATH_ADD);
  type_enum.insert("subtract", NODE_VECTOR_MATH_SUBTRACT);
  type_enum.insert("multiply", NODE_VECTOR_MATH_MULTIPLY);
  type_enum.insert("divide", NODE_VECTOR_MATH_DIVIDE);

  type_enum.insert("cross_product", NODE_VECTOR_MATH_CROSS_PRODUCT);
  type_enum.insert("project", NODE_VECTOR_MATH_PROJECT);
  type_enum.insert("reflect", NODE_VECTOR_MATH_REFLECT);
  type_enum.insert("refract", NODE_VECTOR_MATH_REFRACT);
  type_enum.insert("faceforward", NODE_VECTOR_MATH_FACEFORWARD);
  type_enum.insert("multiply_add", NODE_VECTOR_MATH_MULTIPLY_ADD);

  type_enum.insert("dot_product", NODE_VECTOR_MATH_DOT_PRODUCT);

  type_enum.insert("distance", NODE_VECTOR_MATH_DISTANCE);
  type_enum.insert("length", NODE_VECTOR_MATH_LENGTH);
  type_enum.insert("scale", NODE_VECTOR_MATH_SCALE);
  type_enum.insert("normalize", NODE_VECTOR_MATH_NORMALIZE);

  type_enum.insert("snap", NODE_VECTOR_MATH_SNAP);
  type_enum.insert("round", NODE_VECTOR_MATH_ROUND);
  type_enum.insert("floor", NODE_VECTOR_MATH_FLOOR);
  type_enum.insert("ceil", NODE_VECTOR_MATH_CEIL);
  type_enum.insert("modulo", NODE_VECTOR_MATH_MODULO);
  type_enum.insert("wrap", NODE_VECTOR_MATH_WRAP);
  type_enum.insert("fraction", NODE_VECTOR_MATH_FRACTION);
  type_enum.insert("absolute", NODE_VECTOR_MATH_ABSOLUTE);
  type_enum.insert("power", NODE_VECTOR_MATH_POWER);
  type_enum.insert("sign", NODE_VECTOR_MATH_SIGN);
  type_enum.insert("minimum", NODE_VECTOR_MATH_MINIMUM);
  type_enum.insert("maximum", NODE_VECTOR_MATH_MAXIMUM);

  type_enum.insert("sine", NODE_VECTOR_MATH_SINE);
  type_enum.insert("cosine", NODE_VECTOR_MATH_COSINE);
  type_enum.insert("tangent", NODE_VECTOR_MATH_TANGENT);
  SOCKET_ENUM(math_type, "Type", type_enum, NODE_VECTOR_MATH_ADD);

  SOCKET_IN_VECTOR(vector1, "Vector1", zero_float3());
  SOCKET_IN_VECTOR(vector2, "Vector2", zero_float3());
  SOCKET_IN_VECTOR(vector3, "Vector3", zero_float3());
  SOCKET_IN_FLOAT(scale, "Scale", 1.0f);

  SOCKET_OUT_FLOAT(value, "Value");
  SOCKET_OUT_VECTOR(vector, "Vector");

  return type;
}
