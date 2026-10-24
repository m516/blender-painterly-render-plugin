void SVMCompiler::add_node_data_float(const float f)
{
  current_svm_nodes.push_back_slow(__float_as_int(f));
}
