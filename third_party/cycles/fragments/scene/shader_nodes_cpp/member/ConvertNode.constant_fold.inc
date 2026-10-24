void ConvertNode::constant_fold(const ConstantFolder &folder)
{
  /* proxy nodes should have been removed at this point */
  assert(special_type != SHADER_SPECIAL_TYPE_PROXY);

  if (folder.all_inputs_constant()) {
    if (from == SocketType::FLOAT || from == SocketType::INT) {
      float val = value_float;
      if (from == SocketType::INT) {
        val = value_int;
      }
      if (SocketType::is_float3(to)) {
        folder.make_constant(make_float3(val, val, val));
      }
      else if (to == SocketType::INT) {
        folder.make_constant((int)val);
      }
      else if (to == SocketType::FLOAT) {
        folder.make_constant(val);
      }
    }
    else if (SocketType::is_float3(from)) {
      if (to == SocketType::FLOAT || to == SocketType::INT) {
        float val;
        if (from == SocketType::COLOR) {
          /* color to scalar */
          val = folder.scene->shader_manager->linear_rgb_to_gray(value_color);
        }
        else {
          /* vector/point/normal to scalar */
          val = average(value_vector);
        }
        if (to == SocketType::INT) {
          folder.make_constant((int)val);
        }
        else if (to == SocketType::FLOAT) {
          folder.make_constant(val);
        }
      }
      else if (SocketType::is_float3(to)) {
        folder.make_constant(value_color);
      }
    }
  }
  else {
    ShaderInput *in = inputs[0];
    ShaderNode *prev = in->link->parent;

    /* no-op conversion of A to B to A */
    if (prev->type == get_node_types()[to][from]) {
      ShaderInput *prev_in = prev->inputs[0];

      if (SocketType::is_float3(from) && (to == SocketType::FLOAT || SocketType::is_float3(to)) &&
          prev_in->link)
      {
        folder.bypass(prev_in->link);
      }
    }
  }
}
