NODE_DEFINE(WaveTextureNode)
{
  NodeType *type = NodeType::add("wave_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(WaveTextureNode);

  static NodeEnum type_enum;
  type_enum.insert("bands", NODE_WAVE_BANDS);
  type_enum.insert("rings", NODE_WAVE_RINGS);
  SOCKET_ENUM(wave_type, "Type", type_enum, NODE_WAVE_BANDS);

  static NodeEnum bands_direction_enum;
  bands_direction_enum.insert("x", NODE_WAVE_BANDS_DIRECTION_X);
  bands_direction_enum.insert("y", NODE_WAVE_BANDS_DIRECTION_Y);
  bands_direction_enum.insert("z", NODE_WAVE_BANDS_DIRECTION_Z);
  bands_direction_enum.insert("diagonal", NODE_WAVE_BANDS_DIRECTION_DIAGONAL);
  SOCKET_ENUM(
      bands_direction, "Bands Direction", bands_direction_enum, NODE_WAVE_BANDS_DIRECTION_X);

  static NodeEnum rings_direction_enum;
  rings_direction_enum.insert("x", NODE_WAVE_RINGS_DIRECTION_X);
  rings_direction_enum.insert("y", NODE_WAVE_RINGS_DIRECTION_Y);
  rings_direction_enum.insert("z", NODE_WAVE_RINGS_DIRECTION_Z);
  rings_direction_enum.insert("spherical", NODE_WAVE_RINGS_DIRECTION_SPHERICAL);
  SOCKET_ENUM(
      rings_direction, "Rings Direction", rings_direction_enum, NODE_WAVE_BANDS_DIRECTION_X);

  static NodeEnum profile_enum;
  profile_enum.insert("sine", NODE_WAVE_PROFILE_SIN);
  profile_enum.insert("saw", NODE_WAVE_PROFILE_SAW);
  profile_enum.insert("tri", NODE_WAVE_PROFILE_TRI);
  SOCKET_ENUM(profile, "Profile", profile_enum, NODE_WAVE_PROFILE_SIN);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);
  SOCKET_IN_FLOAT(scale, "Scale", 1.0f);
  SOCKET_IN_FLOAT(distortion, "Distortion", 0.0f);
  SOCKET_IN_FLOAT(detail, "Detail", 2.0f);
  SOCKET_IN_FLOAT(detail_scale, "Detail Scale", 0.0f);
  SOCKET_IN_FLOAT(detail_roughness, "Detail Roughness", 0.5f);
  SOCKET_IN_FLOAT(phase, "Phase Offset", 0.0f);
  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_FLOAT(fac, "Fac");

  return type;
}
