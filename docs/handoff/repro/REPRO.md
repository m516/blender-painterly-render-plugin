# EXP-REPRO: reproduction of experiments 001, 002, 003, 004 and 006

Columns: `identical` = `cmp` exit status 0 against `experiments/<NNN>/<file>`;
`leaf_report_identical`, `n_leaves`, `n_leaves_differing` and `non_numeric_identical` = the
fields of `tools/compare_results.py`'s report on that `results.json` (present only where
`identical` is false).

| experiment | file | identical | leaf_report_identical | n_leaves | n_leaves_differing | non_numeric_identical |
|---|---|---|---|---|---|---|
| 001 | fig_absdiff_P512.png | true |  |  |  |  |
| 001 | fig_image_P512.png | true |  |  |  |  |
| 001 | fig_pixel_major_P64.png | true |  |  |  |  |
| 001 | fig_reference.png | true |  |  |  |  |
| 001 | results.json | false | false | 1798 | 48 | true |
| 002 | fig_alpha_025.png | true |  |  |  |  |
| 002 | fig_alpha_05.png | true |  |  |  |  |
| 002 | fig_alpha_1.png | true |  |  |  |  |
| 002 | fig_ghost_lights.png | true |  |  |  |  |
| 002 | fig_ghost_none.png | true |  |  |  |  |
| 002 | fig_grid.png | true |  |  |  |  |
| 002 | fig_per_path_start.png | true |  |  |  |  |
| 002 | fig_positive.png | true |  |  |  |  |
| 002 | fig_stop_at_emitter.png | true |  |  |  |  |
| 002 | fig_u2_base3.png | true |  |  |  |  |
| 002 | fig_u2_independent.png | true |  |  |  |  |
| 002 | results.json | false | false | 4805 | 80 | true |
| 003 | fig_grid.png | true |  |  |  |  |
| 003 | results.json | false | false | 1278 | 7 | true |
| 004 | fig_grid.png | true |  |  |  |  |
| 004 | results.json | false | false | 2902 | 60 | true |
| 006 | fig_grid_image_plane.png | true |  |  |  |  |
| 006 | fig_grid_pixel.png | true |  |  |  |  |
| 006 | fig_grid_row_image_plane.png | true |  |  |  |  |
| 006 | fig_grid_row_pixel.png | true |  |  |  |  |
| 006 | fig_grid_row_zero.png | true |  |  |  |  |
| 006 | fig_grid_zero.png | true |  |  |  |  |
| 006 | fig_slag_profile.png | true |  |  |  |  |
| 006 | results.json | false | false | 8730 | 2539 | true |

| all_identical | false |
|---|---|
| files | 29 |
| files_identical | 24 |
| files_not_identical | 5 |

Largest difference among the differing leaves of each `results.json` (paths are the tool's
RFC 6901 JSON Pointers; `abs_diff` and `rel_diff` are defined in `tools/compare_results.py`).

| experiment | n_leaves_differing_number | max_abs_diff | max_abs_diff_path | max_rel_diff | max_rel_diff_path |
|---|---|---|---|---|---|
| 001 | 48 | 1.257285475730896e-08 | /h4/convergence/P_ref_ci/1 | 1.8151478847646002e-13 | /h4/convergence/P_ref_ci/1 |
| 002 | 80 | 7.815970093361102e-14 | /effect_size_table/u2_independent/all.spectral_slope | 3.635523510367057e-14 | /effect_summary/alpha_025/all.spectral_slope/mean_a |
| 003 | 7 | 3.3306690738754696e-16 | /h3/test/effect_summary/all.spectral_slope/cohen_d | 2.4107345823333164e-15 | /h3/test/effect_summary/all.spectral_slope/rel_diff |
| 004 | 60 | 2.4868995751603507e-14 | /downsample_effects/all.spectral_slope/cohen_d | 8.760421770679665e-15 | /summary/row_s800/r4.spectral_slope/sd |
| 006 | 2539 | 2.7000623958883807e-13 | /jitter_footprint/comparisons/800/effect_summary/r6.structure_std/cohen_d | 1.2650361197941373e-13 | /hypotheses/H1/image/comparisons/1/effect_summary/r4.slag.y/cohen_d |
