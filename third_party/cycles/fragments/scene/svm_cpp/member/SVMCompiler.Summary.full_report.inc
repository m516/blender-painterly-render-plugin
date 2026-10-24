string SVMCompiler::Summary::full_report() const
{
  string report;
  report += string_printf("Number of SVM nodes: %d\n", num_svm_nodes);
  report += string_printf("Peak stack usage:    %d\n", peak_stack_usage);

  report += string_printf("Time (in seconds):\n");
  report += string_printf("Generate:            %f\n",
                          time_generate_surface + time_generate_bump + time_generate_volume +
                              time_generate_displacement);
  report += string_printf("  Surface:           %f\n", time_generate_surface);
  report += string_printf("  Bump:              %f\n", time_generate_bump);
  report += string_printf("  Volume:            %f\n", time_generate_volume);
  report += string_printf("  Displacement:      %f\n", time_generate_displacement);

  return report;
}
