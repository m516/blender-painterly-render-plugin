void SVMCompiler::generate_multi_closure(ShaderNode *root_node,
                                         ShaderNode *node,
                                         CompilerState *state)
{
  /* only generate once */
  if (state->closure_done.contains(node)) {
    return;
  }

  state->closure_done.insert(node);

  if (node->special_type == SHADER_SPECIAL_TYPE_COMBINE_CLOSURE) {
    /* weighting is already taken care of in ShaderGraph::transform_multi_closure */
    ShaderInput *cl1in = node->input("Closure1");
    ShaderInput *cl2in = node->input("Closure2");
    ShaderInput *facin = node->input("Fac");

    /* skip empty mix/add closure nodes */
    if (!cl1in->link && !cl2in->link) {
      return;
    }

    if (facin && facin->link) {
      /* mix closure: generate instructions to compute mix weight */
      ShaderNodeSet dependencies;
      find_dependencies(dependencies, state->nodes_done, facin);
      generate_svm_nodes(dependencies, state);

      /* execute shared dependencies. this is needed to allow skipping
       * of zero weight closures and their dependencies later, so we
       * ensure that they only skip dependencies that are unique to them */
      ShaderNodeSet cl1deps;
      ShaderNodeSet cl2deps;
      ShaderNodeSet shareddeps;

      find_dependencies(cl1deps, state->nodes_done, cl1in);
      find_dependencies(cl2deps, state->nodes_done, cl2in);

      const ShaderNodeIDComparator node_id_comp;
      set_intersection(cl1deps.begin(),
                       cl1deps.end(),
                       cl2deps.begin(),
                       cl2deps.end(),
                       std::inserter(shareddeps, shareddeps.begin()),
                       node_id_comp);

      /* it's possible some nodes are not shared between this mix node
       * inputs, but still needed to be always executed, this mainly
       * happens when a node of current subbranch is used by a parent
       * node or so */
      if (root_node != node) {
        for (ShaderInput *in : root_node->inputs) {
          ShaderNodeSet rootdeps;
          find_dependencies(rootdeps, state->nodes_done, in, node);
          set_intersection(rootdeps.begin(),
                           rootdeps.end(),
                           cl1deps.begin(),
                           cl1deps.end(),
                           std::inserter(shareddeps, shareddeps.begin()),
                           node_id_comp);
          set_intersection(rootdeps.begin(),
                           rootdeps.end(),
                           cl2deps.begin(),
                           cl2deps.end(),
                           std::inserter(shareddeps, shareddeps.begin()),
                           node_id_comp);
        }
      }

      /* For dependencies AOV nodes, prevent them from being categorized
       * as exclusive deps of one or the other closure, since the need to
       * execute them for AOV writing is not dependent on the closure
       * weights. */
      if (!state->aov_nodes.empty()) {
        set_intersection(state->aov_nodes.begin(),
                         state->aov_nodes.end(),
                         cl1deps.begin(),
                         cl1deps.end(),
                         std::inserter(shareddeps, shareddeps.begin()),
                         node_id_comp);
        set_intersection(state->aov_nodes.begin(),
                         state->aov_nodes.end(),
                         cl2deps.begin(),
                         cl2deps.end(),
                         std::inserter(shareddeps, shareddeps.begin()),
                         node_id_comp);
      }

      if (!shareddeps.empty()) {
        if (cl1in->link) {
          generated_shared_closure_nodes(root_node, cl1in->link->parent, state, shareddeps);
        }
        if (cl2in->link) {
          generated_shared_closure_nodes(root_node, cl2in->link->parent, state, shareddeps);
        }

        generate_svm_nodes(shareddeps, state);
      }

      /* generate instructions for input closure 1 */
      if (cl1in->link) {
        /* Add instruction to skip closure and its dependencies if mix
         * weight is zero.
         */
        const int node_start = current_svm_nodes.size();
        add_node(nullptr, NODE_JUMP_IF_ONE, SVMNodeJumpIfOne{0, stack_assign(facin)});

        generate_multi_closure(root_node, cl1in->link->parent, state);

        /* Fill in jump instruction location to be after closure. */
        const int jump_node_size = 1 + sizeof(SVMNodeJumpIfOne) / sizeof(int);
        current_svm_nodes[node_start + 1] = current_svm_nodes.size() -
                                            (node_start + jump_node_size);
      }

      /* generate instructions for input closure 2 */
      if (cl2in->link) {
        /* Add instruction to skip closure and its dependencies if mix
         * weight is zero.
         */
        const int node_start = current_svm_nodes.size();
        add_node(nullptr, NODE_JUMP_IF_ZERO, SVMNodeJumpIfZero{0, stack_assign(facin)});

        generate_multi_closure(root_node, cl2in->link->parent, state);

        /* Fill in jump instruction location to be after closure. */
        const int jump_node_size = 1 + sizeof(SVMNodeJumpIfZero) / sizeof(int);
        current_svm_nodes[node_start + 1] = current_svm_nodes.size() -
                                            (node_start + jump_node_size);
      }

      /* unassign */
      facin->stack_offset = SVM_STACK_INVALID;
    }
    else {
      /* execute closures and their dependencies, no runtime checks
       * to skip closures here because was already optimized due to
       * fixed weight or add closure that always needs both */
      if (cl1in->link) {
        generate_multi_closure(root_node, cl1in->link->parent, state);
      }
      if (cl2in->link) {
        generate_multi_closure(root_node, cl2in->link->parent, state);
      }
    }
  }
  else {
    generate_closure_node(node, state);
  }

  state->nodes_done.insert(node);
  state->nodes_done_flag[node->id] = true;
}
