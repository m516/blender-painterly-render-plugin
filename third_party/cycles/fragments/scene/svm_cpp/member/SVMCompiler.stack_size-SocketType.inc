int SVMCompiler::stack_size(SocketType::Type type)
{
  int size = 0;

  switch (type) {
    case SocketType::FLOAT:
    case SocketType::INT:
      size = 1;
      break;
    case SocketType::COLOR:
    case SocketType::VECTOR:
    case SocketType::NORMAL:
    case SocketType::POINT:
      size = 3;
      break;
    case SocketType::CLOSURE:
      size = 0;
      break;
    default:
      assert(0);
      break;
  }

  return size;
}
