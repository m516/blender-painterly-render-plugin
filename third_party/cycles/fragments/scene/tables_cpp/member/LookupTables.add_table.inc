size_t LookupTables::add_table(DeviceScene *dscene, vector<float> &data)
{
  assert(!data.empty());

  need_update_ = true;

  Table new_table;
  new_table.offset = 0;
  new_table.size = round_up_to_multiple(data.size(), TABLE_CHUNK_SIZE);

  /* find space to put lookup table */
  list<Table>::iterator table;

  for (table = lookup_tables.begin(); table != lookup_tables.end(); table++) {
    if (new_table.offset + new_table.size <= table->offset) {
      lookup_tables.insert(table, new_table);
      break;
    }
    new_table.offset = table->offset + table->size;
  }

  if (table == lookup_tables.end()) {
    /* add at the end */
    lookup_tables.push_back(new_table);
    dscene->lookup_table.resize(new_table.offset + new_table.size);
  }

  /* copy table data and return offset */
  float *dtable = dscene->lookup_table.data();
  memcpy(dtable + new_table.offset, data.data(), sizeof(float) * data.size());

  return new_table.offset;
}
