SVMStackOffset SVMCompiler::stack_find_offset(const int size)
{
  int offset = -1;

  /* find free space in stack & mark as used */
  for (int i = 0, num_unused = 0; i < SVM_STACK_SIZE; i++) {
    if (active_stack.users[i]) {
      num_unused = 0;
    }
    else {
      num_unused++;
    }

    if (num_unused == size) {
      offset = i + 1 - size;
      max_stack_use = max(i + 1, max_stack_use);

      while (i >= offset) {
        active_stack.users[i--] = 1;
      }

      return offset;
    }
  }

  if (!compile_failed) {
    compile_failed = true;
    LOG_ERROR << "Shader graph: out of SVM stack space, shader \"" << current_shader->name
              << "\" too big.";
  }

  return 0;
}
