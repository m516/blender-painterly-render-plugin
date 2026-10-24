Transform TextureMapping::compute_transform()
{
  Transform mmat = transform_scale(zero_float3());

  if (x_mapping != NONE) {
    mmat[0][x_mapping - 1] = 1.0f;
  }
  if (y_mapping != NONE) {
    mmat[1][y_mapping - 1] = 1.0f;
  }
  if (z_mapping != NONE) {
    mmat[2][z_mapping - 1] = 1.0f;
  }

  float3 scale_clamped = scale;

  if (type == TEXTURE || type == NORMAL) {
    /* keep matrix invertible */
    if (fabsf(scale.x) < 1e-5f) {
      scale_clamped.x = signf(scale.x) * 1e-5f;
    }
    if (fabsf(scale.y) < 1e-5f) {
      scale_clamped.y = signf(scale.y) * 1e-5f;
    }
    if (fabsf(scale.z) < 1e-5f) {
      scale_clamped.z = signf(scale.z) * 1e-5f;
    }
  }

  const Transform smat = transform_scale(scale_clamped);
  const Transform rmat = transform_euler(rotation);
  const Transform tmat = transform_translate(translation);

  Transform mat;

  switch (type) {
    case TEXTURE:
      /* inverse transform on texture coordinate gives
       * forward transform on texture */
      mat = tmat * rmat * smat;
      mat = transform_inverse(mat);
      break;
    case POINT:
      /* full transform */
      mat = tmat * rmat * smat;
      break;
    case VECTOR:
      /* no translation for vectors */
      mat = rmat * smat;
      break;
    case NORMAL:
      /* no translation for normals, and inverse transpose */
      mat = rmat * smat;
      mat = transform_transposed_inverse(mat);
      break;
  }

  /* projection last */
  mat = mat * mmat;

  return mat;
}
