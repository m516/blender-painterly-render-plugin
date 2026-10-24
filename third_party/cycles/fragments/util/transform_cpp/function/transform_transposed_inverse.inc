Transform transform_transposed_inverse(const Transform &tfm)
{
  const ProjectionTransform iprojection(transform_inverse(tfm));
  return projection_to_transform(projection_transpose(iprojection));
}
