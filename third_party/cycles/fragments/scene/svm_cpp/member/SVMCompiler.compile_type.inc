void SVMCompiler::compile_type(Shader *shader, ShaderGraph *graph, ShaderType type)
{
  /* Converting a shader graph into svm_nodes that can be executed
   * sequentially on the virtual machine is fairly simple. We can keep
   * looping over nodes and each time all the inputs of a node are
   * ready, we add svm_nodes for it that read the inputs from the
   * stack and write outputs back to the stack.
   *
   * With the SVM, we always sample only a single closure. We can think
   * of all closures nodes as a binary tree with mix closures as inner
   * nodes and other closures as leafs. The SVM will traverse that tree,
   * each time deciding to go left or right depending on the mix weights,
   * until a closure is found.
   *
   * We only execute nodes that are needed for the mix weights and chosen
   * closure.
   */

  current_type = type;
  current_graph = graph;

  /* get input in output node */
  ShaderNode *output = graph->output();
  ShaderInput *clin = nullptr;

  switch (type) {
    case SHADER_TYPE_SURFACE:
      clin = output->input("Surface");
      break;
    case SHADER_TYPE_VOLUME:
      clin = output->input("Volume");
      break;
    case SHADER_TYPE_DISPLACEMENT:
      clin = output->input("Displacement");
      break;
    case SHADER_TYPE_BUMP:
      clin = output->input("Normal");
      break;
    default:
      assert(0);
      break;
  }

  /* clear all compiler state */
  memset((void *)&active_stack, 0, sizeof(active_stack));
  current_svm_nodes.clear();

  for (ShaderNode *node : graph->nodes) {
    node->added_to_svm = false;
    for (ShaderInput *input : node->inputs) {
      input->stack_offset = SVM_STACK_INVALID;
    }
    for (ShaderOutput *output : node->outputs) {
      output->stack_offset = SVM_STACK_INVALID;
    }
  }

  mark_nodes_requiring_derivatives(*this, graph, type);

  /* for the bump shader we need add a node to store the shader state */
  const bool need_bump_state = (type == SHADER_TYPE_BUMP) &&
                               (shader->get_displacement_method() == DISPLACE_BOTH);
  if (need_bump_state) {
    bump_state_offset = stack_find_offset(SVM_BUMP_EVAL_STATE_SIZE);
    add_node(
        nullptr, NODE_ENTER_BUMP_EVAL, SVMNodeEnterBumpEval{.state_offset = bump_state_offset});
  }

  if (shader->reference_count()) {
    CompilerState state(graph);

    switch (type) {
      case SHADER_TYPE_SURFACE: /* generate surface shader */
        find_aov_nodes_and_dependencies(state.aov_nodes, graph, &state);
        if (shader->has_surface) {
          state.node_feature_mask = KERNEL_FEATURE_NODE_MASK_SURFACE;
        }
        break;
      case SHADER_TYPE_VOLUME: /* generate volume shader */
        if (shader->has_volume) {
          state.node_feature_mask = KERNEL_FEATURE_NODE_MASK_VOLUME;
        }
        break;
      case SHADER_TYPE_DISPLACEMENT: /* generate displacement shader */
        if (shader->has_displacement) {
          state.node_feature_mask = KERNEL_FEATURE_NODE_MASK_DISPLACEMENT;
        }
        break;
      case SHADER_TYPE_BUMP: /* generate bump shader */
        if (clin->link) {
          state.node_feature_mask = KERNEL_FEATURE_NODE_MASK_BUMP;
        }
        break;
      default:
        break;
    }

    if (clin->link) {
      generate_multi_closure(clin->link->parent, clin->link->parent, &state);
    }

    /* compile output node */
    current_node = output;
    output->compile(*this);
    current_node = nullptr;

    if (!state.aov_nodes.empty()) {
      /* AOV passes are only written if the object is directly visible, so
       * there is no point in evaluating all the nodes generated only for the
       * AOV outputs if that's not the case. Therefore, we insert
       * NODE_AOV_START into the shader before the AOV-only nodes are
       * generated which tells the kernel that it can stop evaluation
       * early if AOVs will not be written. */
      add_node(NODE_AOV_START);
      generate_svm_nodes(state.aov_nodes, &state);
    }
  }

  /* add node to restore state after bump shader has finished */
  if (need_bump_state) {
    add_node(
        nullptr, NODE_LEAVE_BUMP_EVAL, SVMNodeLeaveBumpEval{.state_offset = bump_state_offset});
    bump_state_offset = SVM_STACK_INVALID;
  }

  /* if compile failed, generate empty shader */
  if (compile_failed) {
    current_svm_nodes.clear();
    compile_failed = false;
  }

  /* for bump shaders we fall thru to the surface shader, but if this is any other kind of shader
   * it ends here */
  if (type != SHADER_TYPE_BUMP) {
    add_node(NODE_END);
  }
}
