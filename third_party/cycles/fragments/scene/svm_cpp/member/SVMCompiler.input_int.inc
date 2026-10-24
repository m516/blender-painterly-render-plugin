SVMInputInt SVMCompiler::input_int(const char *name)
{
  ShaderInput *input = current_node->input(name);
  SVMInputInt result = {input->parent->get_int(input->socket_type), SVM_STACK_INVALID};
  if (input->link) {
    result.offset = stack_assign(input);
  }
  return result;
}
