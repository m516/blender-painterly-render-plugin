NODE_DEFINE(MathNode)
{
  NodeType *type = NodeType::add("math", create, NodeType::SHADER);

  static NodeEnum type_enum;
  type_enum.insert("add", NODE_MATH_ADD);
  type_enum.insert("subtract", NODE_MATH_SUBTRACT);
  type_enum.insert("multiply", NODE_MATH_MULTIPLY);
  type_enum.insert("divide", NODE_MATH_DIVIDE);
  type_enum.insert("multiply_add", NODE_MATH_MULTIPLY_ADD);
  type_enum.insert("sine", NODE_MATH_SINE);
  type_enum.insert("cosine", NODE_MATH_COSINE);
  type_enum.insert("tangent", NODE_MATH_TANGENT);
  type_enum.insert("sinh", NODE_MATH_SINH);
  type_enum.insert("cosh", NODE_MATH_COSH);
  type_enum.insert("tanh", NODE_MATH_TANH);
  type_enum.insert("arcsine", NODE_MATH_ARCSINE);
  type_enum.insert("arccosine", NODE_MATH_ARCCOSINE);
  type_enum.insert("arctangent", NODE_MATH_ARCTANGENT);
  type_enum.insert("power", NODE_MATH_POWER);
  type_enum.insert("logarithm", NODE_MATH_LOGARITHM);
  type_enum.insert("minimum", NODE_MATH_MINIMUM);
  type_enum.insert("maximum", NODE_MATH_MAXIMUM);
  type_enum.insert("round", NODE_MATH_ROUND);
  type_enum.insert("less_than", NODE_MATH_LESS_THAN);
  type_enum.insert("greater_than", NODE_MATH_GREATER_THAN);
  type_enum.insert("modulo", NODE_MATH_MODULO);
  type_enum.insert("floored_modulo", NODE_MATH_FLOORED_MODULO);
  type_enum.insert("absolute", NODE_MATH_ABSOLUTE);
  type_enum.insert("arctan2", NODE_MATH_ARCTAN2);
  type_enum.insert("floor", NODE_MATH_FLOOR);
  type_enum.insert("ceil", NODE_MATH_CEIL);
  type_enum.insert("fraction", NODE_MATH_FRACTION);
  type_enum.insert("trunc", NODE_MATH_TRUNC);
  type_enum.insert("snap", NODE_MATH_SNAP);
  type_enum.insert("wrap", NODE_MATH_WRAP);
  type_enum.insert("pingpong", NODE_MATH_PINGPONG);
  type_enum.insert("sqrt", NODE_MATH_SQRT);
  type_enum.insert("inversesqrt", NODE_MATH_INV_SQRT);
  type_enum.insert("sign", NODE_MATH_SIGN);
  type_enum.insert("exponent", NODE_MATH_EXPONENT);
  type_enum.insert("radians", NODE_MATH_RADIANS);
  type_enum.insert("degrees", NODE_MATH_DEGREES);
  type_enum.insert("smoothmin", NODE_MATH_SMOOTH_MIN);
  type_enum.insert("smoothmax", NODE_MATH_SMOOTH_MAX);
  type_enum.insert("compare", NODE_MATH_COMPARE);
  SOCKET_ENUM(math_type, "Type", type_enum, NODE_MATH_ADD);

  SOCKET_BOOLEAN(use_clamp, "Use Clamp", false);

  SOCKET_IN_FLOAT(value1, "Value1", 0.5f);
  SOCKET_IN_FLOAT(value2, "Value2", 0.5f);
  SOCKET_IN_FLOAT(value3, "Value3", 0.0f);

  SOCKET_OUT_FLOAT(value, "Value");

  return type;
}
