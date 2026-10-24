NODE_DEFINE(VoronoiTextureNode)
{
  NodeType *type = NodeType::add("voronoi_texture", create, NodeType::SHADER);

  TEXTURE_MAPPING_DEFINE(VoronoiTextureNode);

  static NodeEnum dimensions_enum;
  dimensions_enum.insert("1D", 1);
  dimensions_enum.insert("2D", 2);
  dimensions_enum.insert("3D", 3);
  dimensions_enum.insert("4D", 4);
  SOCKET_ENUM(dimensions, "Dimensions", dimensions_enum, 3);

  static NodeEnum metric_enum;
  metric_enum.insert("euclidean", NODE_VORONOI_EUCLIDEAN);
  metric_enum.insert("manhattan", NODE_VORONOI_MANHATTAN);
  metric_enum.insert("chebychev", NODE_VORONOI_CHEBYCHEV);
  metric_enum.insert("minkowski", NODE_VORONOI_MINKOWSKI);
  SOCKET_ENUM(metric, "Distance Metric", metric_enum, NODE_VORONOI_EUCLIDEAN);

  static NodeEnum feature_enum;
  feature_enum.insert("f1", NODE_VORONOI_F1);
  feature_enum.insert("f2", NODE_VORONOI_F2);
  feature_enum.insert("smooth_f1", NODE_VORONOI_SMOOTH_F1);
  feature_enum.insert("distance_to_edge", NODE_VORONOI_DISTANCE_TO_EDGE);
  feature_enum.insert("n_sphere_radius", NODE_VORONOI_N_SPHERE_RADIUS);
  SOCKET_ENUM(feature, "Feature", feature_enum, NODE_VORONOI_F1);

  SOCKET_BOOLEAN(use_normalize, "Normalize", false);

  SOCKET_IN_POINT(vector, "Vector", zero_float3(), SocketType::LINK_TEXTURE_GENERATED);
  SOCKET_IN_FLOAT(w, "W", 0.0f);
  SOCKET_IN_FLOAT(scale, "Scale", 5.0f);
  SOCKET_IN_FLOAT(detail, "Detail", 0.0f);
  SOCKET_IN_FLOAT(roughness, "Roughness", 0.5f);
  SOCKET_IN_FLOAT(lacunarity, "Lacunarity", 2.0f);
  SOCKET_IN_FLOAT(smoothness, "Smoothness", 5.0f);
  SOCKET_IN_FLOAT(exponent, "Exponent", 0.5f);
  SOCKET_IN_FLOAT(randomness, "Randomness", 1.0f);

  SOCKET_OUT_FLOAT(distance, "Distance");
  SOCKET_OUT_COLOR(color, "Color");
  SOCKET_OUT_POINT(position, "Position");
  SOCKET_OUT_FLOAT(w, "W");
  SOCKET_OUT_FLOAT(radius, "Radius");

  return type;
}
