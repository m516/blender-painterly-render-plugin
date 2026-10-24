static size_t round_up_to_multiple(const size_t size, const size_t chunk)
{
  return ((size + chunk - 1) / chunk) * chunk;
}
