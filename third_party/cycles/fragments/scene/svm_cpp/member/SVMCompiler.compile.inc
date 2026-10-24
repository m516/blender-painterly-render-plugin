void SVMCompiler::compile(Shader *shader, array<int> &svm_nodes, const int index, Summary *summary)
{
  svm_node_types_used[NODE_SHADER_JUMP] = true;
  add_node(nullptr, NODE_SHADER_JUMP, SVMNodeShaderJump{0, 0, 0});
  svm_nodes.append(current_svm_nodes);
  current_svm_nodes.clear();

  /* copy graph for shader with bump mapping */
  const int start_num_svm_nodes = svm_nodes.size();

  const double time_start = time_dt();

  const bool has_bump_from_displacement = shader->has_bump_from_displacement;

  current_shader = shader;

  /* generate bump shader */
  if (has_bump_from_displacement) {
    const scoped_timer timer((summary != nullptr) ? &summary->time_generate_bump : nullptr);
    compile_type(shader, shader->graph.get(), SHADER_TYPE_BUMP);
    svm_nodes[index + 1] = svm_nodes.size();
    svm_nodes.append(current_svm_nodes);
  }

  /* generate surface shader */
  {
    const scoped_timer timer((summary != nullptr) ? &summary->time_generate_surface : nullptr);
    compile_type(shader, shader->graph.get(), SHADER_TYPE_SURFACE);
    /* only set jump offset if there's no bump shader, as the bump shader will fall thru to this
     * one if it exists */
    if (!has_bump_from_displacement) {
      svm_nodes[index + 1] = svm_nodes.size();
    }
    svm_nodes.append(current_svm_nodes);
  }

  /* generate volume shader */
  {
    const scoped_timer timer((summary != nullptr) ? &summary->time_generate_volume : nullptr);
    compile_type(shader, shader->graph.get(), SHADER_TYPE_VOLUME);
    svm_nodes[index + 2] = svm_nodes.size();
    svm_nodes.append(current_svm_nodes);
  }

  /* generate displacement shader */
  {
    const scoped_timer timer((summary != nullptr) ? &summary->time_generate_displacement :
                                                    nullptr);
    compile_type(shader, shader->graph.get(), SHADER_TYPE_DISPLACEMENT);
    svm_nodes[index + 3] = svm_nodes.size();
    svm_nodes.append(current_svm_nodes);
  }

  /* Fill in summary information. */
  if (summary != nullptr) {
    summary->time_total = time_dt() - time_start;
    summary->peak_stack_usage = max_stack_use;
    summary->num_svm_nodes = svm_nodes.size() - start_num_svm_nodes;
  }

  /* Estimate emission for MIS. */
  shader->estimate_emission();
}
