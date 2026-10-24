void SVMCompiler::generate_svm_nodes(const ShaderNodeSet &nodes, CompilerState *state)
{
  ShaderNodeSet &done = state->nodes_done;
  vector<bool> &done_flag = state->nodes_done_flag;

  /* Schedule the nodes to reduce peak SVM stack usage with a Sethi-Ullman style
   * heuristic. This is optimal for trees, but only a heuristic for DAGs where
   * it's an NP-hard problem.
   *
   * Nodes whose sub-graphs need the most stack are generated first, which helps
   * complete tightly related sub-graphs before handling other parts of the graph.
   *
   * See "Generalizations of the Sethi-Ullman algorithm for register allocation"
   * by Appel and Supowit for details. We use different terminology as some of it
   * conflicts with our own.
   *
   * The Sethi-Ullman number is the peak SVM stack size needed to evaluate a node
   * and "producer" nodes feeding into it, including the node output stack size.
   *
   * It was proven that evaluating producer nodes by descending order of this number
   * minus the output stack size is optimal for trees. For a graph, we approximate
   * this by only counting the output stack size for a producer node with multiple
   * consumers. */

  /* Producer nodes feeding into #node that have not been scheduled yet. */
  auto get_producers = [&](const ShaderNode *node, vector<ShaderNode *> &producers) {
    producers.clear();
    for (const ShaderInput *input : node->inputs) {
      if (input->link) {
        ShaderNode *producer = input->link->parent;
        if (!done_flag[producer->id] &&
            std::find(producers.begin(), producers.end(), producer) == producers.end())
        {
          producers.push_back(producer);
        }
      }
    }
  };

  /* Number of unique unscheduled consumer nodes for each producer node. */
  unordered_map<const ShaderNode *, int> num_consumers;
  vector<ShaderNode *> consumers;
  for (ShaderNode *node : nodes) {
    if (done_flag[node->id]) {
      continue;
    }
    consumers.clear();
    for (const ShaderOutput *output : node->outputs) {
      for (const ShaderInput *in : output->links) {
        ShaderNode *consumer = in->parent;
        if (!done_flag[consumer->id] && nodes.contains(consumer) &&
            std::find(consumers.begin(), consumers.end(), consumer) == consumers.end())
        {
          consumers.push_back(consumer);
        }
      }
    }
    num_consumers[node] = consumers.size();
  }

  /* Sethi-Ullman number for each node. */
  unordered_map<const ShaderNode *, int> sethi_ullman_number;

  /* Current Sethi-Ullman number for graph scheduling, only counting the output
   * size when there are multiple consumers. */
  auto current_sethi_ullman_number = [&](ShaderNode *node) -> int {
    return (num_consumers[node] > 1) ? stack_node_output_size(node) : sethi_ullman_number[node];
  };

  /* Order producers by Sethi-Ullman number. Node ID is the tie breaker. */
  auto node_order_key = [&](ShaderNode *node) -> int {
    return current_sethi_ullman_number(node) - stack_node_output_size(node);
  };
  auto node_order_compare = [&](ShaderNode *a, ShaderNode *b) {
    return node_order_key(a) > node_order_key(b) ||
           (node_order_key(a) == node_order_key(b) && a->id < b->id);
  };

  /* Compute Sethi-Ullman number recursively. */
  std::function<int(ShaderNode *)> compute_sethi_ullman_number = [&](ShaderNode *node) -> int {
    const auto it = sethi_ullman_number.find(node);
    if (it != sethi_ullman_number.end()) {
      return it->second;
    }

    vector<ShaderNode *> producers;
    get_producers(node, producers);
    for (ShaderNode *producer : producers) {
      compute_sethi_ullman_number(producer);
    }
    std::sort(producers.begin(), producers.end(), node_order_compare);

    /* Sum output and peak stack usage of producers. */
    int output_size = 0;
    int peak_size = 0;
    for (ShaderNode *producer : producers) {
      peak_size = max(peak_size, output_size + current_sethi_ullman_number(producer));
      output_size += stack_node_output_size(producer);
    }
    peak_size = max(peak_size, output_size + stack_node_output_size(node));
    sethi_ullman_number[node] = peak_size;

    return peak_size;
  };

  /* Gather all sink nodes (that have no unscheduled consumers) and sort by
   * Sethi-Ullman number. */
  vector<ShaderNode *> sinks;
  for (ShaderNode *node : nodes) {
    if (done_flag[node->id]) {
      continue;
    }
    compute_sethi_ullman_number(node);
    bool is_sink = true;
    for (const ShaderOutput *output : node->outputs) {
      for (const ShaderInput *in : output->links) {
        if (!done_flag[in->parent->id] && nodes.contains(in->parent)) {
          is_sink = false;
          break;
        }
      }
      if (!is_sink) {
        break;
      }
    }
    if (is_sink) {
      sinks.push_back(node);
    }
  }
  std::sort(sinks.begin(), sinks.end(), node_order_compare);

  /* Generate nodes recursively from sink nodes. */
  std::function<void(ShaderNode *)> generate = [&](ShaderNode *node) {
    if (done_flag[node->id]) {
      return;
    }
    vector<ShaderNode *> producers;
    get_producers(node, producers);
    std::sort(producers.begin(), producers.end(), node_order_compare);
    for (ShaderNode *producer : producers) {
      generate(producer);
    }
    generate_node(node, done);
    done.insert(node);
    done_flag[node->id] = true;
  };

  for (ShaderNode *node : sinks) {
    generate(node);
  }
}
