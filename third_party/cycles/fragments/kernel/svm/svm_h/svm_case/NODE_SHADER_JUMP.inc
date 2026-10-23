      SVM_CASE(NODE_SHADER_JUMP)
      {
        const SVMNodeShaderJump jump = svm_node_get<SVMNodeShaderJump>(kg, &offset);
        if (type == SHADER_TYPE_SURFACE) {
          offset = jump.offset_surface;
        }
        else if (type == SHADER_TYPE_VOLUME) {
          offset = jump.offset_volume;
        }
        else if (type == SHADER_TYPE_DISPLACEMENT) {
          offset = jump.offset_displacement;
        }
        else {
          return;
        }
        break;
      }
