"""The generated properties, panels, presets, operator and version handler of the add-on.

The properties of ``scene.painterly`` are generated from ``_painterly.integrator_sockets()``
(T4.2), so the checks here compare them with that reflection rather than with a second list of
expected values: a knob's default, type, limits and enum items live in the core, and the add-on
may not restate them.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import _painterly
import bpy
import pytest

from painterly import operators, presets, properties, ui, version_update


def setting_names() -> list[str]:
    """Every property of ``scene.painterly``: the sockets, then the hand-written settings."""
    return [socket["name"] for socket in _painterly.integrator_sockets()] + list(
        properties.HAND_WRITTEN_ANNOTATIONS
    )


@pytest.fixture()
def settings(addon: ModuleType):
    """``scene.painterly``, reset to the generated defaults before and after each test."""
    group = bpy.context.scene.painterly
    for name in setting_names():
        group.property_unset(name)
    yield group
    for name in setting_names():
        group.property_unset(name)


def test_scene_painterly_is_the_registered_group(addon: ModuleType) -> None:
    assert isinstance(bpy.context.scene.painterly, properties.PainterlyRenderSettings)
    assert bpy.context.scene.painterly.bl_rna.identifier == "PainterlyRenderSettings"


def test_every_socket_is_a_property_with_the_reflected_default(settings) -> None:
    """Each socket's name, default and value type come from the reflection, unchanged."""
    for socket in _painterly.integrator_sockets():
        name = socket["name"]
        assert hasattr(settings, name), name
        value = getattr(settings, name)
        if socket["type"] == "vector":
            value = tuple(value)
        elif socket["type"] == "float":
            value = float(value)
        elif socket["type"] == "boolean":
            value = bool(value)
        elif socket["type"] in ("int", "uint"):
            value = int(value)
        assert value == socket["default"], name
        assert isinstance(value, type(socket["default"])) or socket["type"] in ("int", "uint"), name


def test_property_types_follow_the_socket_types(settings) -> None:
    """The RNA type of every generated property is the one its socket type names.

    Blender reports a ``FloatVectorProperty`` as ``FLOAT`` with ``array_length`` 3, so a vector
    socket is checked by both.
    """
    expected_rna_type = {
        "boolean": "BOOLEAN",
        "int": "INT",
        "uint": "INT",
        "float": "FLOAT",
        "enum": "ENUM",
        "vector": "FLOAT",
    }
    for socket in _painterly.integrator_sockets():
        rna = settings.bl_rna.properties[socket["name"]]
        assert rna.type == expected_rna_type[socket["type"]], socket["name"]
        if socket["type"] == "vector":
            assert rna.array_length == 3, socket["name"]


def test_ui_name_and_description_come_from_the_reflection(settings) -> None:
    for socket in _painterly.integrator_sockets():
        rna = settings.bl_rna.properties[socket["name"]]
        assert rna.name == socket["ui_name"], socket["name"]
        assert rna.description == socket["description"], socket["name"]


def test_enum_identifiers_are_the_socket_items_in_order(settings) -> None:
    """The enum items are the socket's identifiers, in the order the reflection reports them."""
    for socket in _painterly.integrator_sockets():
        if socket["type"] != "enum":
            continue
        rna = settings.bl_rna.properties[socket["name"]]
        identifiers = [item.identifier for item in rna.enum_items]
        assert identifiers == socket["enum_items"], socket["name"]
        assert rna.default == socket["default"], socket["name"]


def test_enum_labels_are_the_identifier_in_title_case(settings) -> None:
    """An enum label is the identifier with underscores as spaces, in title case (card T4.2)."""
    for socket in _painterly.integrator_sockets():
        if socket["type"] != "enum":
            continue
        rna = settings.bl_rna.properties[socket["name"]]
        for item in rna.enum_items:
            assert item.name == item.identifier.replace("_", " ").title(), item.identifier


def test_enum_values_round_trip(settings) -> None:
    """Every identifier of every enum socket can be set and read back."""
    for socket in _painterly.integrator_sockets():
        if socket["type"] != "enum":
            continue
        for identifier in socket["enum_items"]:
            setattr(settings, socket["name"], identifier)
            assert getattr(settings, socket["name"]) == identifier
        setattr(settings, socket["name"], socket["default"])


def test_the_spiral_rotation_is_an_euler_vector(settings) -> None:
    """``spiral_rotation`` is the one vector socket with a subtype: an XYZ Euler rotation."""
    rna = settings.bl_rna.properties["spiral_rotation"]
    assert rna.type == "FLOAT"
    assert rna.subtype == "EULER"
    assert rna.array_length == 3

    for socket in _painterly.integrator_sockets():
        if socket["type"] != "vector" or socket["name"] == "spiral_rotation":
            continue
        assert settings.bl_rna.properties[socket["name"]].subtype == "NONE", socket["name"]


def test_int_limits_come_from_the_reflection(settings) -> None:
    """A reflected limit becomes the property's limit, clamped to Blender's int32 range.

    An unreflected limit falls back to Blender's own: 0 for a uint's minimum, and the int32 bound
    on the side the reflection leaves open.
    """
    for socket in _painterly.integrator_sockets():
        if socket["type"] not in ("int", "uint"):
            continue
        rna = settings.bl_rna.properties[socket["name"]]
        low = properties.BLENDER_INT_MIN if socket["type"] == "int" else 0
        expected_min = low if socket["min"] is None else max(low, int(socket["min"]))
        expected_max = (
            properties.BLENDER_INT_MAX
            if socket["max"] is None
            else min(properties.BLENDER_INT_MAX, int(socket["max"]))
        )
        assert rna.hard_min == expected_min, socket["name"]
        assert rna.hard_max == expected_max, socket["name"]


def test_uint_sockets_stay_inside_blender_int32(settings) -> None:
    """A uint socket is a Blender int, so its property is clamped to the int32 range."""
    for socket in _painterly.integrator_sockets():
        if socket["type"] != "uint":
            continue
        rna = settings.bl_rna.properties[socket["name"]]
        assert rna.hard_min == 0, socket["name"]
        assert rna.hard_max == properties.BLENDER_INT_MAX, socket["name"]


def test_int_builder_clamps_an_unreflected_uint_and_a_wide_int() -> None:
    """The int builder itself clamps, not only the limits that the reflection happens to report."""
    unreflected_uint = properties._int_property(
        {
            "name": "u",
            "type": "uint",
            "default": 0,
            "min": None,
            "max": None,
            "soft_min": None,
            "soft_max": None,
            "ui_name": "U",
            "description": "",
        }
    )
    assert unreflected_uint.keywords["min"] == 0
    assert unreflected_uint.keywords["max"] == properties.BLENDER_INT_MAX

    signed = properties._int_property(
        {
            "name": "i",
            "type": "int",
            "default": 0,
            "min": -(2**40),
            "max": 2**40,
            "soft_min": None,
            "soft_max": None,
            "ui_name": "I",
            "description": "",
        }
    )
    assert signed.keywords["min"] == properties.BLENDER_INT_MIN
    assert signed.keywords["max"] == properties.BLENDER_INT_MAX

    limited = properties._int_property(
        {
            "name": "l",
            "type": "uint",
            "default": 1,
            "min": -5.0,
            "max": 22.0,
            "soft_min": None,
            "soft_max": None,
            "ui_name": "L",
            "description": "",
        }
    )
    assert limited.keywords["min"] == 0
    assert limited.keywords["max"] == 22


def test_no_hand_written_property_is_a_socket(settings) -> None:
    """No default is written twice: the hand-written names are exactly the non-knob settings."""
    socket_names = {socket["name"] for socket in _painterly.integrator_sockets()}
    assert not socket_names & set(properties.HAND_WRITTEN_ANNOTATIONS)

    hand_written = set(properties.HAND_WRITTEN_ANNOTATIONS)
    assert set(properties.PainterlyRenderSettings.__annotations__) == socket_names | hand_written


def test_the_hand_written_properties_are_what_the_addon_needs(settings) -> None:
    """The four Blender-only settings and the hidden data version, with their defaults."""
    assert settings.batch == 1
    assert settings.threads == 0
    assert settings.spiral_object is None
    assert settings.reference_scene is False
    assert settings.data_version == 0
    assert settings.bl_rna.properties["data_version"].is_hidden


def test_batch_and_threads_accept_their_documented_ranges(settings) -> None:
    """``batch`` is at least 1 and ``threads`` at least 0; Blender clamps a value outside them."""
    settings.batch = 4
    settings.threads = 3
    assert (settings.batch, settings.threads) == (4, 3)

    assert settings.bl_rna.properties["batch"].hard_min == 1
    assert settings.bl_rna.properties["threads"].hard_min == 0

    settings.batch = 0
    settings.threads = -1
    assert (settings.batch, settings.threads) == (1, 0)


def test_socket_groups_cover_every_socket_once() -> None:
    """The UI groups partition the sockets, in socket order, as the reflection reports them."""
    reflected = [(socket["group"], socket["name"]) for socket in _painterly.integrator_sockets()]
    grouped = [(group, name) for group, names in properties.SOCKET_GROUPS.items() for name in names]
    assert grouped == reflected


def test_the_five_panels_are_registered(addon: ModuleType) -> None:
    for cls in ui.classes:
        assert getattr(bpy.types, cls.__name__) is cls, cls.__name__
        assert cls.bl_context == "render"
        assert cls.bl_space_type == "PROPERTIES"
        assert cls.bl_region_type == "WINDOW"


def test_one_panel_per_socket_group(addon: ModuleType) -> None:
    """The five panels are the reflection's five groups, in order."""
    labels = [cls.bl_label for cls in ui.classes]
    assert labels == list(properties.SOCKET_GROUPS)


def test_the_panels_poll_for_our_engine(addon: ModuleType) -> None:
    scene = bpy.context.scene
    previous = scene.render.engine
    try:
        scene.render.engine = "PAINTERLY"
        assert bpy.context.engine == "PAINTERLY"
        for cls in ui.classes:
            assert cls.poll(bpy.context), cls.__name__

        scene.render.engine = "BLENDER_EEVEE"
        for cls in ui.classes:
            assert not cls.poll(bpy.context), cls.__name__
    finally:
        scene.render.engine = previous


class RecordingLayout:
    """A stand-in for a panel layout that records the properties it is asked to draw."""

    def __init__(self) -> None:
        self.properties: list[str] = []
        self.use_property_split = False

    def prop(self, data, name: str, **kwargs) -> None:  # noqa: ARG002 - Blender's signature
        self.properties.append(name)


class FakePanel:
    """A stand-in for a panel instance: its ``draw`` only reads ``self.layout``."""

    def __init__(self) -> None:
        self.layout = RecordingLayout()


def test_drawing_a_panel_shows_its_group_in_socket_order(addon: ModuleType) -> None:
    """Each panel draws its socket group in socket order, with split properties."""
    panel_extras = {
        "RENDER_PT_painterly_sampling": ["batch", "threads"],
        "RENDER_PT_painterly_brush": ["spiral_object"],
        "RENDER_PT_painterly_path": [],
        "RENDER_PT_painterly_lights": [],
        "RENDER_PT_painterly_film": ["reference_scene"],
    }
    for cls in ui.classes:
        panel = FakePanel()
        cls.draw(panel, bpy.context)
        assert panel.layout.use_property_split
        assert panel.layout.properties == (
            list(properties.SOCKET_GROUPS[cls.bl_label]) + panel_extras[cls.__name__]
        ), cls.__name__


def test_get_panels_lends_the_render_panels_and_excludes_simplify(addon: ModuleType) -> None:
    """``get_panels()`` is Blender's ``BLENDER_RENDER`` set without our exclude set."""
    panels = ui.get_panels()
    names = {panel.__name__ for panel in panels}

    assert names
    assert "RENDER_PT_simplify" not in names
    assert "RENDER_PT_simplify" in ui.EXCLUDE_PANELS
    assert all("BLENDER_RENDER" in panel.COMPAT_ENGINES for panel in panels)
    assert all("PAINTERLY" in panel.COMPAT_ENGINES for panel in panels)


def test_the_excluded_panel_is_not_lent_to_our_engine(addon: ModuleType) -> None:
    for name in ui.EXCLUDE_PANELS:
        panel = getattr(bpy.types, name)
        assert "PAINTERLY" not in panel.COMPAT_ENGINES, name


def test_unregistering_drops_our_engine_from_the_borrowed_panels(addon: ModuleType) -> None:
    """``ui.unregister()`` removes ``PAINTERLY`` again; ``ui.register()`` puts it back."""
    borrowed = [panel for panel in ui.get_panels() if "PAINTERLY" in panel.COMPAT_ENGINES]
    assert borrowed

    ui.unregister()
    try:
        assert all("PAINTERLY" not in panel.COMPAT_ENGINES for panel in ui.get_panels())
        assert not hasattr(bpy.types, ui.classes[0].__name__)
    finally:
        ui.register()

    assert all("PAINTERLY" in panel.COMPAT_ENGINES for panel in ui.get_panels())


def test_the_preset_menu_has_an_operator_to_draw_its_entries() -> None:
    """``PresetPanel.draw()`` reads ``preset_operator``; without it the popover raises."""
    panel = presets.PAINTERLY_PT_render_presets
    assert panel.preset_operator == "script.execute_preset"
    assert panel.preset_add_operator == presets.PAINTERLY_OT_render_preset_add.bl_idname
    assert panel.preset_subdir == presets.PRESET_SUBDIR


def test_the_preset_menu_lists_the_shipped_preset(addon: ModuleType) -> None:
    """Drawing the menu offers the shipped preset, through the operator it names."""

    class RecordingOperator:
        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

    class RecordingMenuLayout(RecordingLayout):
        def __init__(self) -> None:
            super().__init__()
            self.operators: list[tuple[str, dict]] = []
            self.emboss = None
            self.operator_context = None

        def column(self, align=False):  # noqa: ARG002 - Blender's signature
            return self

        def row(self, align=False):  # noqa: ARG002 - Blender's signature
            return self

        def operator(self, idname: str, **kwargs):
            self.operators.append((idname, kwargs))
            return RecordingOperator()

        def label(self, text: str = "", **kwargs) -> None:  # noqa: ARG002 - Blender's signature
            pass

        def separator(self) -> None:
            pass

    class MenuStandIn:
        """The menu panel's own attributes, with Blender's ``path_menu`` behind them."""

        layout = RecordingMenuLayout()
        bl_idname = "PAINTERLY_PT_render_presets"
        preset_subdir = presets.PAINTERLY_PT_render_presets.preset_subdir
        preset_operator = presets.PAINTERLY_PT_render_presets.preset_operator
        preset_add_operator = presets.PAINTERLY_PT_render_presets.preset_add_operator
        path_menu = bpy.types.Menu.path_menu

    presets.PAINTERLY_PT_render_presets.draw(MenuStandIn(), bpy.context)

    drawn = [idname for idname, _ in MenuStandIn.layout.operators]
    assert presets.PAINTERLY_PT_render_presets.preset_operator in drawn
    assert presets.PAINTERLY_OT_render_preset_add.bl_idname in drawn


def test_the_preset_path_is_registered(addon: ModuleType) -> None:
    """The add-on's directory is a preset root, and unregistering takes it away again."""

    def preset_directories() -> list[Path]:
        return [Path(path) for path in bpy.utils.preset_paths(presets.PRESET_SUBDIR)]

    assert preset_file().parent in preset_directories()
    assert preset_file().is_file()

    presets.unregister()
    try:
        assert preset_file().parent not in preset_directories()
    finally:
        presets.register()

    assert preset_file().parent in preset_directories()


def test_the_preset_stores_every_setting_that_can_be_stored() -> None:
    """A saved preset carries every socket and every portable hand-written setting."""
    stored = set(presets.PAINTERLY_OT_render_preset_add.preset_values)
    for name in properties.SOCKET_NAMES:
        assert f"painterly.{name}" in stored, name
    assert "painterly.batch" in stored
    assert "painterly.threads" in stored
    assert "painterly.reference_scene" in stored
    assert "painterly.spiral_object" not in stored
    assert "painterly.data_version" not in stored


def preset_file() -> Path:
    """The shipped ``smallpaint_reference`` preset."""
    return (
        Path(presets.PRESET_PATH) / "presets" / presets.PRESET_SUBDIR / ("smallpaint_reference.py")
    )


def test_the_shipped_preset_exists() -> None:
    assert preset_file().is_file()


def test_the_shipped_preset_sets_the_reference_configuration(settings) -> None:
    """The preset selects smallpaint's image chain and reference scene, and resets two defaults."""
    settings.chain = "lane"
    settings.reference_scene = False
    settings.output_mode = "scene_linear"
    settings.passes = 3

    path = preset_file()
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), {"bpy": bpy})

    assert settings.chain == "image"
    assert settings.reference_scene is True
    # `property_unset()` restores the generated default, so the preset does not pin a pass count.
    assert not settings.is_property_set("passes")
    assert not settings.is_property_set("output_mode")
    reflected = {socket["name"]: socket["default"] for socket in _painterly.integrator_sockets()}
    assert settings.passes == reflected["passes"]
    assert settings.output_mode == reflected["output_mode"]


def test_the_shipped_preset_touches_no_lights(settings) -> None:
    """The built-in reference scene carries smallpaint's own emission (SPEC §6): no light knob."""
    lights = {
        socket["name"] for socket in _painterly.integrator_sockets() if socket["group"] == "Lights"
    }
    assert lights
    text = preset_file().read_text(encoding="utf-8")
    for name in lights:
        assert f"painterly.{name}" not in text, name


class RecordingOperatorContext:
    """The operator's ``self``: records the reports it makes."""

    def __init__(self) -> None:
        self.reports: list[tuple[set[str], str]] = []

    def report(self, level: set[str], message: str) -> None:
        self.reports.append((level, message))


def test_the_operator_applies_smallpaints_display_settings(settings) -> None:
    """The operator sets the Standard view transform, no look, 0 exposure, gamma 1, dither 0."""
    scene = bpy.context.scene
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.5
    scene.view_settings.gamma = 2.0
    scene.render.dither_intensity = 1.0

    operator = RecordingOperatorContext()
    assert operators.PAINTERLY_OT_apply_display_settings.execute(operator, bpy.context) == {
        "FINISHED"
    }

    assert scene.view_settings.view_transform == "Standard"
    assert scene.view_settings.look == "None"
    assert scene.view_settings.exposure == 0.0
    assert scene.view_settings.gamma == 1.0
    assert scene.render.dither_intensity == 0.0

    assert len(operator.reports) == 1
    level, message = operator.reports[0]
    assert "INFO" in level
    # The report names what it changed; `look` was already "None", so it is not listed.
    for name in ("view_transform", "exposure", "gamma", "dither_intensity"):
        assert name in message, name


def test_the_operator_reports_when_nothing_changes(settings) -> None:
    scene = bpy.context.scene
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.dither_intensity = 0.0

    operator = RecordingOperatorContext()
    assert operators.PAINTERLY_OT_apply_display_settings.execute(operator, bpy.context) == {
        "FINISHED"
    }
    assert len(operator.reports) == 1
    _, message = operator.reports[0]
    assert "already match" in message


# Blender calls a ``version_update`` handler with an argument that is not a scene: bpy 5.2.2 passes
# ``None`` when a file is loaded. The handler must take its scenes from ``bpy.data.scenes``, so the
# tests below pass the same argument instead of a scene, which would hide that (M4-FIX-T4.2a).
VERSION_HANDLER_ARGUMENT = None


@pytest.fixture()
def second_scene(addon: ModuleType):
    """A second scene, as a file saved with more than one scene has; removed after the test."""
    scene = bpy.data.scenes.new("second scene")
    yield scene
    bpy.data.scenes.remove(scene)


def test_the_version_handler_is_registered_and_persistent() -> None:
    assert version_update.do_versions in bpy.app.handlers.version_update
    assert hasattr(version_update.do_versions, "_bpy_persistent")


def test_the_version_handler_upgrades_an_old_file(settings) -> None:
    settings.data_version = 0
    version_update.do_versions(VERSION_HANDLER_ARGUMENT)
    assert settings.data_version == version_update.CURRENT_DATA_VERSION == 1


def test_the_version_handler_upgrades_every_scene(second_scene, settings) -> None:
    """The handler ignores its argument and upgrades each scene of ``bpy.data.scenes``."""
    settings.data_version = 0
    second_scene.painterly.data_version = 0

    version_update.do_versions(VERSION_HANDLER_ARGUMENT)

    assert settings.data_version == version_update.CURRENT_DATA_VERSION == 1
    assert second_scene.painterly.data_version == version_update.CURRENT_DATA_VERSION


def test_the_version_handler_leaves_a_current_or_newer_file(settings) -> None:
    settings.data_version = version_update.CURRENT_DATA_VERSION
    version_update.do_versions(VERSION_HANDLER_ARGUMENT)
    assert settings.data_version == version_update.CURRENT_DATA_VERSION

    settings.data_version = version_update.CURRENT_DATA_VERSION + 1
    version_update.do_versions(VERSION_HANDLER_ARGUMENT)
    assert settings.data_version == version_update.CURRENT_DATA_VERSION + 1


def test_unregistering_the_version_handler_removes_it(addon: ModuleType) -> None:
    version_update.unregister()
    try:
        assert version_update.do_versions not in bpy.app.handlers.version_update
    finally:
        version_update.register()
    assert version_update.do_versions in bpy.app.handlers.version_update
