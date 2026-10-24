SVMStackOffset SVMCompiler::stack_assign(ShaderInput *input)
{
  /* stack offset assign? */
  if (input->stack_offset == SVM_STACK_INVALID) {
    if (input->link) {
      /* linked to output -> use output offset */
      assert(input->link->stack_offset != SVM_STACK_INVALID);
      input->stack_offset = input->link->stack_offset;
    }
    else {
      ShaderNode *node = input->parent;

      /* not linked to output -> add nodes to load default value */
      input->stack_offset = stack_find_offset(input);

      if (input->type() == SocketType::FLOAT) {
        add_value_node(node, node->get_float(input->socket_type), input->stack_offset);
      }
      else if (input->type() == SocketType::INT) {
        add_value_node(
            node, __int_as_float(node->get_int(input->socket_type)), input->stack_offset);
      }
      else if (input->type() == SocketType::VECTOR || input->type() == SocketType::NORMAL ||
               input->type() == SocketType::POINT || input->type() == SocketType::COLOR)
      {
        add_value_node(node, node->get_float3(input->socket_type), input->stack_offset);
      }
      else { /* should not get called for closure */
        assert(0);
      }
    }
  }

  return input->stack_offset;
}
