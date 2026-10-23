      SVM_CASE(NODE_JUMP_IF_ZERO)
      {
        const SVMNodeJumpIfZero jump = svm_node_get<SVMNodeJumpIfZero>(kg, &offset);
        if (stack_load_float(stack, jump.stack_offset) <= 0.0f) {
          offset += jump.jump_offset;
        }
      }
      break;
