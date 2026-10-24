void LookupTables::remove_table(size_t *offset)
{
  if (*offset == TABLE_OFFSET_INVALID) {
    /* The table isn't even allocated, so just return here. */
    return;
  }

  need_update_ = true;

  list<Table>::iterator table;

  for (table = lookup_tables.begin(); table != lookup_tables.end(); table++) {
    if (table->offset == *offset) {
      lookup_tables.erase(table);
      *offset = TABLE_OFFSET_INVALID;
      return;
    }
  }

  assert(table != lookup_tables.end());
}
