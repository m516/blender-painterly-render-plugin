void MathNode::constant_fold(const ConstantFolder &folder)
{
  if (folder.all_inputs_constant()) {
    folder.make_constant(svm_math(math_type, value1, value2, value3));
  }
  else {
    folder.fold_math(math_type);
  }
}
