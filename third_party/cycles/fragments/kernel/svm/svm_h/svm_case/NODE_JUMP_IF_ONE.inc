      SVM_CASE(NODE_JUMP_IF_ONE)
      {
        const SVMNodeJumpIfOne jump = svm_node_get<SVMNodeJumpIfOne>(kg, &offset);
        if (stack_load_float(stack, jump.stack_offset) >= 1.0f) {
          offset += jump.jump_offset;
        }
      }
      break;
