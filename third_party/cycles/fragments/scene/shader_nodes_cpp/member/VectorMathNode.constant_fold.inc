void VectorMathNode::constant_fold(const ConstantFolder &folder)
{
  float value = 0.0f;
  float3 vector = zero_float3();

  if (folder.all_inputs_constant()) {
    svm_vector_math(&value, &vector, math_type, vector1, vector2, vector3, scale);
    if (folder.output == output("Value")) {
      folder.make_constant(value);
    }
    else if (folder.output == output("Vector")) {
      folder.make_constant(vector);
    }
  }
  else {
    folder.fold_vector_math(math_type);
  }
}
