const NodeType *(&ConvertNode::get_node_types())[ConvertNode::MAX_TYPE][ConvertNode::MAX_TYPE]
{
  static const NodeType *node_types[MAX_TYPE][MAX_TYPE];
  static std::once_flag node_types_flag;

  std::call_once(node_types_flag, [&] {
    const int num_types = 8;
    const SocketType::Type types[num_types] = {SocketType::FLOAT,
                                               SocketType::INT,
                                               SocketType::COLOR,
                                               SocketType::VECTOR,
                                               SocketType::POINT,
                                               SocketType::NORMAL,
                                               SocketType::STRING,
                                               SocketType::CLOSURE};

    for (size_t i = 0; i < num_types; i++) {
      const SocketType::Type from = types[i];
      const ustring from_name(SocketType::type_name(from));
      const ustring from_value_name("value_" + from_name.string());

      for (size_t j = 0; j < num_types; j++) {
        const SocketType::Type to = types[j];
        const ustring to_name(SocketType::type_name(to));
        const ustring to_value_name("value_" + to_name.string());

        const string node_name = "convert_" + from_name.string() + "_to_" + to_name.string();
        NodeType *type = NodeType::add(node_name.c_str(), create, NodeType::SHADER);

        type->register_input(from_value_name,
                             from_value_name,
                             from,
                             SOCKET_OFFSETOF(ConvertNode, value_float),
                             SocketType::zero_default_value(),
                             nullptr,
                             nullptr,
                             SocketType::LINKABLE);
        type->register_output(to_value_name, to_value_name, to);

        assert(from < MAX_TYPE);
        assert(to < MAX_TYPE);

        node_types[from][to] = type;
      }
    }
  });

  return node_types;
}
