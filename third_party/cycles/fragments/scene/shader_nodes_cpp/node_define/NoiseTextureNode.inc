NODE_DEFINE(NoiseTextureNode)
{
  NodeType *type = NodeType::add("noise_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(NoiseTextureNode);

  static NodeEnum dimensions_enum;
  dimensions_enum.insert("1D", 1);
  dimensions_enum.insert("2D", 2);
  dimensions_enum.insert("3D", 3);
  dimensions_enum.insert("4D", 4);
  SOCKET_ENUM(dimensions, "Dimensions", dimensions_enum, 3);

  static NodeEnum type_enum;
  type_enum.insert("multifractal", NODE_NOISE_MULTIFRACTAL);
  type_enum.insert("fBM", NODE_NOISE_FBM);
  type_enum.insert("hybrid_multifractal", NODE_NOISE_HYBRID_MULTIFRACTAL);
  type_enum.insert("ridged_multifractal", NODE_NOISE_RIDGED_MULTIFRACTAL);
  type_enum.insert("hetero_terrain", NODE_NOISE_HETERO_TERRAIN);
  SOCKET_ENUM(type, "Type", type_enum, NODE_NOISE_FBM);

  SOCKET_BOOLEAN(use_normalize, "Normalize", true);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);
  SOCKET_IN_FLOAT(w, "W", 0.0f);
  SOCKET_IN_FLOAT(scale, "Scale", 1.0f);
  SOCKET_IN_FLOAT(detail, "Detail", 2.0f);
  SOCKET_IN_FLOAT(roughness, "Roughness", 0.5f);
  SOCKET_IN_FLOAT(lacunarity, "Lacunarity", 2.0f);
  SOCKET_IN_FLOAT(offset, "Offset", 0.0f);
  SOCKET_IN_FLOAT(gain, "Gain", 1.0f);
  SOCKET_IN_FLOAT(distortion, "Distortion", 0.0f);

  SOCKET_OUT_FLOAT(fac, "Fac");
  SOCKET_OUT_COLOR(color, "Color");

  return type;
}
