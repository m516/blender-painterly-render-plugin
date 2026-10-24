bool TextureMapping::skip()
{
  if (translation != zero_float3()) {
    return false;
  }
  if (rotation != zero_float3()) {
    return false;
  }
  if (scale != one_float3()) {
    return false;
  }

  if (x_mapping != X || y_mapping != Y || z_mapping != Z) {
    return false;
  }
  if (use_minmax) {
    return false;
  }

  return true;
}
