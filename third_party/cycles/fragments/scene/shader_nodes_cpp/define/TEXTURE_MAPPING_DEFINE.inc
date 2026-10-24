#define TEXTURE_MAPPING_DEFINE(TextureNode) \
  SOCKET_POINT(tex_mapping.translation, "Translation", zero_float3()); \
  SOCKET_VECTOR(tex_mapping.rotation, "Rotation", zero_float3()); \
  SOCKET_VECTOR(tex_mapping.scale, "Scale", one_float3()); \
\
  SOCKET_VECTOR(tex_mapping.min, "Min", make_float3(-FLT_MAX, -FLT_MAX, -FLT_MAX)); \
  SOCKET_VECTOR(tex_mapping.max, "Max", make_float3(FLT_MAX, FLT_MAX, FLT_MAX)); \
  SOCKET_BOOLEAN(tex_mapping.use_minmax, "Use Min Max", false); \
\
  static NodeEnum mapping_axis_enum; \
  mapping_axis_enum.insert("none", TextureMapping::NONE); \
  mapping_axis_enum.insert("x", TextureMapping::X); \
  mapping_axis_enum.insert("y", TextureMapping::Y); \
  mapping_axis_enum.insert("z", TextureMapping::Z); \
  SOCKET_ENUM(tex_mapping.x_mapping, "x_mapping", mapping_axis_enum, TextureMapping::X); \
  SOCKET_ENUM(tex_mapping.y_mapping, "y_mapping", mapping_axis_enum, TextureMapping::Y); \
  SOCKET_ENUM(tex_mapping.z_mapping, "z_mapping", mapping_axis_enum, TextureMapping::Z); \
\
  static NodeEnum mapping_type_enum; \
  mapping_type_enum.insert("point", TextureMapping::POINT); \
  mapping_type_enum.insert("texture", TextureMapping::TEXTURE); \
  mapping_type_enum.insert("vector", TextureMapping::VECTOR); \
  mapping_type_enum.insert("normal", TextureMapping::NORMAL); \
  SOCKET_ENUM(tex_mapping.type, "Type", mapping_type_enum, TextureMapping::TEXTURE); \
\
  static NodeEnum mapping_projection_enum; \
  mapping_projection_enum.insert("flat", TextureMapping::FLAT); \
  mapping_projection_enum.insert("cube", TextureMapping::CUBE); \
  mapping_projection_enum.insert("tube", TextureMapping::TUBE); \
  mapping_projection_enum.insert("sphere", TextureMapping::SPHERE); \
  SOCKET_ENUM(tex_mapping.projection, "Projection", mapping_projection_enum, TextureMapping::FLAT);
