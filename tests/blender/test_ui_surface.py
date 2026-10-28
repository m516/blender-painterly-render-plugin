"""The engine's render pass, the Film panel's display settings and presets, and the knobs' activity.

Every expected value here comes from a source outside the code under test: Blender 5.2.2's own
``scripts/startup/bl_ui/`` panels and its ``bl_operators/presets.py``, Cycles' add-on at v5.2.2
(``.cache/vendor/blender-v5.2.2/intern/cycles/blender/addon/``), the SPEC sections the activity
table cites, and the manifest's version. Nothing is taken from the output of the code under test.

Each test requests the ``addon`` fixture itself, because only that fixture registers the add-on
(M4-FIX-TQ5c makes it autouse; this file does not rely on that), and restores every setting it
changes, so the render tests that share the default scene are unaffected.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import _painterly
import bpy
import pytest

from painterly import engine, operators, presets, properties, ui

# The two outputs of a Render Layers node that the engine's Combined pass provides: Blender's own
# names for a registered ``RGBA``/``COLOR`` pass, which the test also reads from the same node on a
# ``BLENDER_EEVEE`` scene, so the expected names come from Blender rather than from our code.
RENDER_LAYER_OUTPUTS = ("Image", "Alpha")

# The two versions the version check names, for the child process of the F23 test. The wrong
# version is a literal that no manifest declares; the right one is read from the manifest below.
CHILD_WRONG_VERSION = "0.0.0"

# The child process of the F23 test: load the add-on package exactly as
# ``tests/blender/conftest.py`` does, with a native module whose version differs from the
# manifest's and which has no ``integrator_sockets``, then load the package and register it. It
# prints the ImportError's message.
CHILD_SCRIPT = """
import importlib.util
import sys

module_dir, addon_dir, wrong_version = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, module_dir)

import _painterly

_painterly.version_info = lambda: {"version": wrong_version}
del _painterly.integrator_sockets

spec = importlib.util.spec_from_file_location(
    "painterly", addon_dir + "/__init__.py", submodule_search_locations=[addon_dir]
)
module = importlib.util.module_from_spec(spec)
sys.modules["painterly"] = module
try:
    spec.loader.exec_module(module)
    module.register()
except ImportError as exc:
    print(exc)
else:
    raise SystemExit("the add-on loaded a native module of another version")
"""


def setting_names() -> list[str]:
    """Every property of ``scene.painterly``: the sockets, then the hand-written settings."""
    return [socket["name"] for socket in _painterly.integrator_sockets()] + list(
        properties.HAND_WRITTEN_ANNOTATIONS
    )


def preset_setting_names() -> list[str]:
    """The property names that a preset stores, without the ``painterly.`` prefix."""
    return [path.removeprefix("painterly.") for path in presets.PRESET_VALUES]


@pytest.fixture()
def settings(addon: ModuleType):
    """``scene.painterly``, unset to the generated defaults before and after each test."""
    group = bpy.context.scene.painterly
    for name in setting_names():
        group.property_unset(name)
    yield group
    for name in setting_names():
        group.property_unset(name)


@pytest.fixture()
def matching_display_settings(addon: ModuleType):
    """The display settings of SPEC §8, with the scene's own restored afterwards.

    Yields:
        A dict from ``(owner, name)`` to the value the scene held before the test.
    """
    scene = bpy.context.scene
    saved = {
        (entry.owner, entry.name): getattr(getattr(scene, entry.owner), entry.name)
        for entry in operators.DISPLAY_SETTINGS
    }
    for entry in operators.DISPLAY_SETTINGS:
        setattr(getattr(scene, entry.owner), entry.name, entry.value)
    yield saved
    for (owner, name), value in saved.items():
        setattr(getattr(scene, owner), name, value)


class Records:
    """What a draw asked the layout to draw, in drawing order."""

    def __init__(self) -> None:
        self.properties: list[tuple[str, bool]] = []
        self.labels: list[tuple[str, bool]] = []
        self.operators: list[str] = []
        self.popovers: list[str] = []
        self.separators = 0

    def active_of(self, name: str) -> bool:
        """The ``active`` flag of the sub-layout that drew the property ``name``."""
        flags = [active for drawn, active in self.properties if drawn == name]
        assert len(flags) == 1, f"{name} was drawn {len(flags)} times"
        return flags[0]


class RecordingLayout:
    """A stand-in for a panel layout that records the properties, labels and operators it draws.

    A sub-layout (``row()``, ``column()``) records into the same :class:`Records` as its parent and
    starts with its parent's ``active`` and ``alert`` flags, as Blender's sub-layouts do, so a
    property drawn through one is recorded in drawing order as if drawn directly.
    """

    def __init__(self, records: Records | None = None, active: bool = True, alert: bool = False):
        self.records = Records() if records is None else records
        self.active = active
        self.alert = alert
        self.use_property_split = False
        self.use_property_decorate = True
        self.emboss = None
        self.operator_context = None

    def prop(self, data, name: str, **kwargs) -> None:  # noqa: ARG002 - Blender's signature
        self.records.properties.append((name, self.active))

    def row(self, **kwargs) -> RecordingLayout:  # noqa: ARG002 - Blender's signature
        return RecordingLayout(self.records, self.active, self.alert)

    def column(self, **kwargs) -> RecordingLayout:  # noqa: ARG002 - Blender's signature
        return RecordingLayout(self.records, self.active, self.alert)

    def label(self, text: str = "", **kwargs) -> None:  # noqa: ARG002 - Blender's signature
        self.records.labels.append((text, self.alert))

    def operator(self, idname: str, **kwargs) -> None:  # noqa: ARG002 - Blender's signature
        self.records.operators.append(idname)

    def popover(self, panel: str, **kwargs) -> None:  # noqa: ARG002 - Blender's signature
        self.records.popovers.append(panel)

    def separator(self) -> None:
        self.records.separators += 1


class FakePanel:
    """A stand-in for a panel instance: a ``draw`` only reads ``self.layout``."""

    def __init__(self) -> None:
        self.layout = RecordingLayout()


def draw_panel(cls) -> Records:
    """Draw ``cls`` with a recording layout and return what it recorded."""
    panel = FakePanel()
    cls.draw(panel, bpy.context)
    return panel.layout.records


def draw_header_preset(cls) -> Records:
    """Draw the header preset of ``cls`` with a recording layout and return what it recorded."""
    panel = FakePanel()
    cls.draw_header_preset(panel, bpy.context)
    return panel.layout.records


def panel_drawing(name: str):
    """The panel class whose ``draw`` draws the property ``name``."""
    for group, names in properties.SOCKET_GROUPS.items():
        if name in names:
            return next(cls for cls in ui.classes if cls.bl_label == group)
    hand_written = {"batch": "Sampling", "threads": "Sampling", "spiral_object": "Brush"}
    label = hand_written[name]
    return next(cls for cls in ui.classes if cls.bl_label == label)


def property_value(settings, name: str):
    """A setting's value, with a vector property as a tuple (Blender returns an ``Euler``)."""
    value = getattr(settings, name)
    return tuple(value) if hasattr(value, "__len__") and not isinstance(value, str) else value


def preset_file() -> Path:
    """The shipped ``smallpaint_reference`` preset."""
    return (
        Path(presets.PRESET_PATH) / "presets" / presets.PRESET_SUBDIR / ("smallpaint_reference.py")
    )


# --------------------------------------------------------------------------------------------
# TQ.5 F1: the engine registers its Combined pass.
# --------------------------------------------------------------------------------------------


def test_the_compositor_layers_node_has_the_engines_outputs(addon: ModuleType) -> None:
    """A Render Layers node on a PAINTERLY scene has the Image and Alpha outputs of a render pass.

    Blender builds the node's outputs from the passes that ``update_render_passes`` registers, so an
    engine that registers none gives the node no outputs at all. The node is made as Blender's own
    tracking operator makes it (``bl_operators/clip.py:708-723`` on 5.2.2).
    """
    scene = bpy.context.scene
    previous_engine = scene.render.engine
    previous_group = scene.compositing_node_group
    previous_use_compositing = scene.render.use_compositing
    trees = []

    def layer_outputs(engine: str) -> list[tuple[str, bool]]:
        scene.render.engine = engine
        tree = bpy.data.node_groups.new(f"Painterly test tree {engine}", "CompositorNodeTree")
        trees.append(tree)
        scene.compositing_node_group = tree
        node = tree.nodes.new(type="CompositorNodeRLayers")
        return [(output.name, output.enabled) for output in node.outputs]

    try:
        reference = layer_outputs("BLENDER_EEVEE")
        outputs = layer_outputs("PAINTERLY")

        assert [name for name, _ in reference] == list(RENDER_LAYER_OUTPUTS)
        assert outputs == reference
    finally:
        scene.render.engine = previous_engine
        scene.compositing_node_group = previous_group
        scene.render.use_compositing = previous_use_compositing
        for tree in trees:
            bpy.data.node_groups.remove(tree)


# --------------------------------------------------------------------------------------------
# TQ.5 F2: the Film panel reaches the operator, warns while the settings differ, and has a preset
# popover in its header.
# --------------------------------------------------------------------------------------------


def test_the_film_panel_draws_the_display_settings_operator(
    addon: ModuleType, settings, matching_display_settings
) -> None:
    """The panel's button is the operator's idname, after a separator."""
    records = draw_panel(ui.RENDER_PT_painterly_film)
    assert operators.PAINTERLY_OT_apply_display_settings.bl_idname in records.operators
    assert records.separators >= 1


def test_the_film_panel_warns_while_the_display_settings_differ(
    addon: ModuleType, settings, matching_display_settings
) -> None:
    """Under ``display_referred``, a view transform or dither the operator would change warns.

    AgX and dither 1.0 are Blender 5.2.2's defaults for a new scene (``bpy.context.scene`` on a
    factory start-up), and both differ from what SPEC §8's display-referred mode needs.
    """
    scene = bpy.context.scene
    settings.output_mode = "display_referred"

    scene.view_settings.view_transform = "AgX"
    records = draw_panel(ui.RENDER_PT_painterly_film)
    assert [alert for _, alert in records.labels] == [True], records.labels
    assert records.labels[0][0], "the warning says nothing"

    scene.view_settings.view_transform = "Standard"
    scene.render.dither_intensity = 1.0
    records = draw_panel(ui.RENDER_PT_painterly_film)
    assert [alert for _, alert in records.labels] == [True], records.labels


def test_the_film_panel_does_not_warn_once_the_settings_match(
    addon: ModuleType, settings, matching_display_settings
) -> None:
    """After the operator ran, or under ``scene_linear``, the panel draws no warning row."""
    settings.output_mode = "display_referred"
    bpy.context.scene.view_settings.view_transform = "AgX"
    assert draw_panel(ui.RENDER_PT_painterly_film).labels

    assert bpy.ops.render.painterly_apply_display_settings() == {"FINISHED"}
    assert draw_panel(ui.RENDER_PT_painterly_film).labels == []

    settings.output_mode = "scene_linear"
    bpy.context.scene.view_settings.view_transform = "AgX"
    assert draw_panel(ui.RENDER_PT_painterly_film).labels == []


def test_the_film_panel_header_draws_the_preset_popover(
    addon: ModuleType, matching_display_settings
) -> None:
    """``draw_header_preset`` draws the preset panel's popover, as Cycles' header presets do."""
    records = draw_header_preset(ui.RENDER_PT_painterly_film)
    assert records.popovers == [presets.PAINTERLY_PT_render_presets.__name__]


# --------------------------------------------------------------------------------------------
# TQ.5 F12: the draws switch the animation decorator off.
# --------------------------------------------------------------------------------------------


def test_every_draw_switches_the_animation_decorator_off(
    addon: ModuleType, settings, matching_display_settings
) -> None:
    """Each of the five draws sets ``use_property_decorate = False``, as Cycles' panels do."""
    for cls in ui.classes:
        panel = FakePanel()
        cls.draw(panel, bpy.context)
        assert panel.layout.use_property_decorate is False, cls.__name__
        assert panel.layout.use_property_split is True, cls.__name__


# --------------------------------------------------------------------------------------------
# TQ.5 F18: one activity table, and every property drawn through the helper that reads it.
# --------------------------------------------------------------------------------------------

# The entries of the activity table, each with its source, and no others (M4-FIX-TQ5a, TQ.5 F18).
ACTIVITY_ENTRIES = {
    "diffuse_gain": ("reference_scene", (False, True), (True, False)),
    "emission_gain": ("reference_scene", (False, True), (True, False)),
    "ray_epsilon": ("reference_scene", (False, True), (True, False)),
    "max_depth": ("reference_scene", (False, True), (True, False)),
    "spiral_frame": ("reference_scene", (False, True), (True, False)),
    "lane_length": ("chain", ("lane", True), ("row", False)),
    "k0_phase_lock_bits": ("chain", ("row", True), ("image", False)),
    "exposure": ("output_mode", ("scene_linear", True), ("display_referred", False)),
    "spiral_rotation": ("spiral_frame", ("camera", True), ("smallpaint", False)),
    "spiral_object": ("spiral_frame", ("object", True), ("camera", False)),
}


def test_the_activity_table_has_exactly_the_entries_that_have_a_mode(
    addon: ModuleType, settings
) -> None:
    """The table's keys are the ten knobs whose effect depends on another setting, and no others."""
    assert set(ui.ACTIVITY) == set(ACTIVITY_ENTRIES)


@pytest.mark.parametrize("name", sorted(ACTIVITY_ENTRIES))
def test_a_knob_without_an_effect_in_the_current_mode_is_drawn_inactive(
    addon: ModuleType, settings, matching_display_settings, name: str
) -> None:
    """For each entry, the controlling setting's two values give the two ``active`` flags."""
    controlling, (active_value, active_flag), (inactive_value, inactive_flag) = ACTIVITY_ENTRIES[
        name
    ]
    cls = panel_drawing(name)

    setattr(settings, controlling, active_value)
    assert draw_panel(cls).active_of(name) is active_flag, (name, active_value)

    setattr(settings, controlling, inactive_value)
    assert draw_panel(cls).active_of(name) is inactive_flag, (name, inactive_value)


def test_a_knob_outside_the_table_is_always_active(addon: ModuleType, settings) -> None:
    """A property with no entry keeps its layout's ``active``, whatever the mode."""
    settings.chain = "image"
    settings.reference_scene = True
    records = draw_panel(ui.RENDER_PT_painterly_path)
    assert records.active_of("alpha") is True


# --------------------------------------------------------------------------------------------
# TQ.5 F29: the preset file carries the add-on's SPDX header.
# --------------------------------------------------------------------------------------------


def test_the_preset_file_opens_with_the_spdx_header(addon: ModuleType) -> None:
    """The preset's first two lines are ``film.py``'s: Blender runs presets with ``execfile``."""
    film_header = Path(properties.__file__).with_name("film.py").read_text(encoding="utf-8")
    preset_header = preset_file().read_text(encoding="utf-8")
    assert preset_header.splitlines()[:2] == film_header.splitlines()[:2]


# --------------------------------------------------------------------------------------------
# TQ.5 F30: the Light tab's Preview panel is not lent to the engine.
# --------------------------------------------------------------------------------------------


def test_the_light_preview_panel_is_not_lent(addon: ModuleType) -> None:
    """``DATA_PT_preview`` is excluded by name: the engine declares no previews."""
    assert "DATA_PT_preview" in ui.EXCLUDE_PANELS
    assert "PAINTERLY" not in bpy.types.DATA_PT_preview.COMPAT_ENGINES


# --------------------------------------------------------------------------------------------
# TQ.5 F20: the operator's settings are what Blender 5.2.2 applies to the displayed bytes.
# --------------------------------------------------------------------------------------------

# One non-matching value per setting of the operator's list: the three the item adds, plus the five
# the operator already had. AgX, 0.5, 2.0 and dither 1.0 are Blender 5.2.2's defaults for a new
# scene; "Display P3" is a display colour space of its own in the OCIO config
# (``datafiles/colormanagement/config.ocio:69-70``).
NON_MATCHING_DISPLAY_SETTINGS = {
    "view_transform": "AgX",
    "look": "AgX - Punchy",
    "exposure": 0.5,
    "gamma": 2.0,
    "dither_intensity": 1.0,
    "display_device": "Display P3",
    "use_curve_mapping": True,
    "use_white_balance": True,
}


class RecordingOperatorContext:
    """The operator's ``self``: records the reports it makes."""

    def __init__(self) -> None:
        self.reports: list[tuple[set[str], str]] = []

    def report(self, level: set[str], message: str) -> None:
        self.reports.append((level, message))


def test_the_operator_restores_every_setting_it_names(
    addon: ModuleType, matching_display_settings
) -> None:
    """Each of the eight settings set away from its target is restored and named in the report."""
    scene = bpy.context.scene
    assert set(NON_MATCHING_DISPLAY_SETTINGS) == {
        entry.name for entry in operators.DISPLAY_SETTINGS
    }

    for entry in operators.DISPLAY_SETTINGS:
        setattr(getattr(scene, entry.owner), entry.name, NON_MATCHING_DISPLAY_SETTINGS[entry.name])

    operator = RecordingOperatorContext()
    assert operators.PAINTERLY_OT_apply_display_settings.execute(operator, bpy.context) == {
        "FINISHED"
    }

    for entry in operators.DISPLAY_SETTINGS:
        assert getattr(getattr(scene, entry.owner), entry.name) == entry.value, entry.name

    assert len(operator.reports) == 1
    level, message = operator.reports[0]
    assert "INFO" in level
    for entry in operators.DISPLAY_SETTINGS:
        assert entry.name in message, entry.name


def test_the_operator_reports_when_the_display_settings_already_match(
    addon: ModuleType, matching_display_settings
) -> None:
    """With all eight at their target the operator changes nothing and says so."""
    operator = RecordingOperatorContext()
    assert operators.PAINTERLY_OT_apply_display_settings.execute(operator, bpy.context) == {
        "FINISHED"
    }
    assert len(operator.reports) == 1
    assert "already match" in operator.reports[0][1]


def test_the_comparison_function_names_the_settings_that_differ(
    addon: ModuleType, matching_display_settings
) -> None:
    """``differing_display_settings`` is the operator's and the warning row's one comparison."""
    scene = bpy.context.scene
    assert operators.differing_display_settings(scene) == ()

    scene.view_settings.use_white_balance = True
    scene.display_settings.display_device = "Display P3"
    assert [entry.name for entry in operators.differing_display_settings(scene)] == [
        "display_device",
        "use_white_balance",
    ]


def test_the_display_settings_operator_runs_through_blender(
    addon: ModuleType, matching_display_settings
) -> None:
    """The registered operator finishes when Blender calls it."""
    bpy.context.scene.view_settings.view_transform = "AgX"
    assert bpy.ops.render.painterly_apply_display_settings() == {"FINISHED"}
    assert bpy.context.scene.view_settings.view_transform == "Standard"


# --------------------------------------------------------------------------------------------
# TQ.5 F11: the preset returns every knob it does not name to its default.
# --------------------------------------------------------------------------------------------


def test_the_shipped_preset_leaves_every_knob_it_does_not_name_at_its_default(
    addon: ModuleType, settings
) -> None:
    """Applying the shipped preset sets ``chain`` and ``reference_scene`` and nothing else.

    The preset panel's ``reset_cb`` runs before the file (Blender 5.2.2
    ``bl_operators/presets.py:299``), so the knobs the file does not name are unset and read their
    generated defaults; the file's own two ``property_unset()`` calls keep that true for a direct
    ``exec`` (``test_properties.py``).
    """
    menu = bpy.types.PAINTERLY_PT_render_presets
    saved_label = menu.bl_label
    settings.jitter = 0.5
    settings.seed = 3
    settings.alpha = 0.5
    settings.lane_length = 4
    settings.passes = 7
    try:
        assert bpy.ops.script.execute_preset(
            filepath=str(preset_file()), menu_idname="PAINTERLY_PT_render_presets"
        ) == {"FINISHED"}
    finally:
        menu.bl_label = saved_label

    stored = preset_setting_names()
    assert {name for name in stored if settings.is_property_set(name)} == {
        "chain",
        "reference_scene",
    }

    reflected = {socket["name"]: socket["default"] for socket in _painterly.integrator_sockets()}
    for name in stored:
        if name in ("chain", "reference_scene"):
            continue
        if name in reflected:
            expected = reflected[name]
            if isinstance(expected, (list, tuple)):
                expected = tuple(expected)
            assert property_value(settings, name) == expected, name
        else:
            # `batch` and `threads` are hand-written settings, so their default is not in the
            # socket reflection; the property's own RNA default is the one the add-on declares.
            assert getattr(settings, name) == settings.bl_rna.properties[name].default, name


def test_the_reset_cb_unsets_every_preset_setting(addon: ModuleType, settings) -> None:
    """``reset_cb(context, filepath)`` returns each stored setting to unset."""
    for name in preset_setting_names():
        setattr(settings, name, getattr(settings, name))
    assert all(settings.is_property_set(name) for name in preset_setting_names())

    presets.PAINTERLY_PT_render_presets.reset_cb(bpy.context, str(preset_file()))

    assert not any(settings.is_property_set(name) for name in preset_setting_names())


# --------------------------------------------------------------------------------------------
# TQ.5 F38: the add-preset operator round-trips every stored setting.
# --------------------------------------------------------------------------------------------


def test_the_add_preset_operator_round_trips_every_setting(
    addon: ModuleType, settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A preset the add operator writes restores every ``PRESET_VALUES`` setting when applied.

    ``AddPresetBase.execute`` asks ``bpy.utils.user_resource`` where to write (Blender 5.2.2
    ``bl_operators/presets.py:149``), so that call is redirected into a temporary directory:
    nothing may be written under the developer's Blender profile.
    """
    user_resource = bpy.utils.user_resource

    def temporary_user_resource(kind, *args, path=None, create=False, **kwargs):
        if kind != "SCRIPTS":
            return user_resource(kind, *args, path=path, create=create, **kwargs)
        directory = tmp_path / path
        if create:
            directory.mkdir(parents=True, exist_ok=True)
        return str(directory)

    monkeypatch.setattr(bpy.utils, "user_resource", temporary_user_resource)
    menu = bpy.types.PAINTERLY_PT_render_presets
    saved_label = menu.bl_label

    saved = {
        "chain": "lane",
        "lane_length": 8,
        "seed": 7,
        "seed_per_frame": True,
        "passes": 32,
        "spiral_frame": "world",
        "spiral_rotation": (0.0, 0.5, 0.0),
        "u2_mode": "independent",
        "k0_phase_lock_bits": 3,
        "alpha": 0.25,
        "max_depth": 12,
        "diffuse_gain": 0.5,
        "emission_gain": 4.0,
        "continue_after_emitter": False,
        "ray_epsilon": 0.001,
        "two_sided": False,
        "emission_scale": 2.0,
        "ghost_lights": False,
        "output_mode": "scene_linear",
        "exposure": 3.0,
        "jitter": 0.5,
        "batch": 3,
        "threads": 2,
        "reference_scene": True,
    }
    assert set(saved) == set(preset_setting_names())
    for name, value in saved.items():
        setattr(settings, name, value)
    snapshot = {name: property_value(settings, name) for name in saved}

    try:
        assert bpy.ops.render.painterly_render_preset_add(name="Painterly Test Preset") == {
            "FINISHED"
        }
    finally:
        menu.bl_label = saved_label

    # `AddPresetBase` asks for the SCRIPTS resource with `presets/<subdir>`, which the stand-in
    # maps under the temporary directory.
    written = sorted((tmp_path / "presets" / presets.PRESET_SUBDIR).glob("*.py"))
    assert len(written) == 1
    for name in preset_setting_names():
        assert f"painterly.{name} = " in written[0].read_text(encoding="utf-8"), name

    # Other values, so that the preset has to restore every setting: unset each one (the generated
    # default) and change two of them again.
    for name in saved:
        settings.property_unset(name)
    settings.chain = "row"
    settings.exposure = 2.0
    assert any(property_value(settings, name) != value for name, value in snapshot.items())

    assert bpy.ops.script.execute_preset(
        filepath=str(written[0]), menu_idname="PAINTERLY_PT_render_presets"
    ) == {"FINISHED"}

    for name, value in snapshot.items():
        assert property_value(settings, name) == value, name


# --------------------------------------------------------------------------------------------
# TQ.5 F23: the version check runs when ``engine`` is imported.
# --------------------------------------------------------------------------------------------


def test_a_mismatched_native_module_fails_at_import_with_both_versions(
    addon: ModuleType, tmp_path: Path
) -> None:
    """Loading the package with a native module of another version raises ImportError, naming both.

    The child loads the package as ``tests/blender/conftest.py`` does, with
    ``_painterly.version_info`` patched and ``integrator_sockets`` deleted from the module, which
    is what a stale module looks like.
    """
    manifest = Path(properties.__file__).with_name("blender_manifest.toml")
    with manifest.open("rb") as handle:
        declared = tomllib.load(handle)["version"]
    assert declared != CHILD_WRONG_VERSION

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            CHILD_SCRIPT,
            str(Path(_painterly.__file__).parent),
            str(Path(addon.__file__).parent),
            CHILD_WRONG_VERSION,
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert CHILD_WRONG_VERSION in result.stdout
    assert declared in result.stdout
    assert "ImportError" not in result.stdout


def test_init_calls_the_same_version_check(
    addon: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``init()`` calls the check that the import ran, rather than a second copy of it."""
    calls = []
    monkeypatch.setattr(engine, "check_native_version", lambda: calls.append(True))
    engine.init()
    assert calls == [True]
