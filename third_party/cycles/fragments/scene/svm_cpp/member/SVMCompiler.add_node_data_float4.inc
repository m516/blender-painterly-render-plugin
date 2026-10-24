void SVMCompiler::add_node_data_float4(const float4 &f)
{
  current_svm_nodes.push_back_slow(__float_as_int(f.x));
  current_svm_nodes.push_back_slow(__float_as_int(f.y));
  current_svm_nodes.push_back_slow(__float_as_int(f.z));
  current_svm_nodes.push_back_slow(__float_as_int(f.w));
}
