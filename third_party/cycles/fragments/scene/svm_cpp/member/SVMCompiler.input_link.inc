SVMStackOffset SVMCompiler::input_link(const char *name)
{
  /* This is for sockets like normal which always expect a link. For the constant_folded_in we have
   * to write the value to the stack with another load and return a linked svm offset, as these
   * never store the default value in the SVMNode. */
  ShaderInput *input = current_node->input(name);
  /* Ensure input link is pushed to SVM before the node itself. */
  assert(!(current_node->added_to_svm && input->constant_folded_in && input->link == nullptr &&
           input->stack_offset == SVM_STACK_INVALID));
  return (input->link || input->constant_folded_in) ? stack_assign(input) : SVM_STACK_INVALID;
}
