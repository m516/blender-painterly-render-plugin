NODE_DEFINE(VectorTransformNode)
{
  NodeType *type = NodeType::add("vector_transform", create, NodeType::SHADER);

  static NodeEnum type_enum;
  type_enum.insert("vector", NODE_VECTOR_TRANSFORM_TYPE_VECTOR);
  type_enum.insert("point", NODE_VECTOR_TRANSFORM_TYPE_POINT);
  type_enum.insert("normal", NODE_VECTOR_TRANSFORM_TYPE_NORMAL);
  SOCKET_ENUM(transform_type, "Type", type_enum, NODE_VECTOR_TRANSFORM_TYPE_VECTOR);

  static NodeEnum space_enum;
  space_enum.insert("world", NODE_VECTOR_TRANSFORM_CONVERT_SPACE_WORLD);
  space_enum.insert("object", NODE_VECTOR_TRANSFORM_CONVERT_SPACE_OBJECT);
  space_enum.insert("camera", NODE_VECTOR_TRANSFORM_CONVERT_SPACE_CAMERA);
  SOCKET_ENUM(convert_from, "Convert From", space_enum, NODE_VECTOR_TRANSFORM_CONVERT_SPACE_WORLD);
  SOCKET_ENUM(convert_to, "Convert To", space_enum, NODE_VECTOR_TRANSFORM_CONVERT_SPACE_OBJECT);

  SOCKET_IN_VECTOR(vector, "Vector", zero_float3());
  SOCKET_OUT_VECTOR(vector, "Vector");

  return type;
}
