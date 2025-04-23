bl_info = {
    "name": "EFT Weapon Mod Attacher",
    "blender": (3, 0, 0),
    "category": "Object",
}

import bpy
import os
import json
import string
import re
import bpy.app.timers

def ensure_eft_shader_loaded():
    shader_name = "EFT Shader v1"
    if shader_name in bpy.data.node_groups:
        print(f"[EFT Addon] Node group '{shader_name}' already loaded.")
        return

    addon_dir = os.path.dirname(__file__)
    blend_path = os.path.join(addon_dir, "EFT_Shader.blend")

    if not os.path.exists(blend_path):
        print(f"[EFT Addon] .blend not found: {blend_path}")
        return

    print(f"[EFT Addon] Attempting to load from {blend_path}")

    try:
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
            # 🛠 Fix: Accessing node_groups must be explicit
            if hasattr(data_from, "node_groups") and shader_name in data_from.node_groups:
                data_to.node_groups = [shader_name]
                print(f"[EFT Addon] Successfully loaded shader: {shader_name}")
            else:
                print(f"[EFT Addon] Shader '{shader_name}' not found in .blend file")
    except Exception as e:
        print(f"[EFT Addon] Error loading shader group: {e}")



# --- CLEAR OUT OLD DYNAMIC PROPS ---
def clear_mod_props():
    for attr in dir(bpy.types.Scene):
        if attr.startswith("mod_"):
            try:
                delattr(bpy.types.Scene, attr)
            except:
                pass

# Global caches
weapon_mod_data = {}
weapon_compat_data = {}
bone_items_cache = []


def load_mod_data(root):
    global weapon_mod_data
    base = os.path.abspath(root)
    weapon_mod_data = {}
    try:
        for category in os.listdir(base):
            cat_path = os.path.join(base, category)
            if os.path.isdir(cat_path):
                weapon_mod_data[category] = [
                    d for d in os.listdir(cat_path)
                    if os.path.isdir(os.path.join(cat_path, d))
                ]
        print(f"Scanned mod folders in '{base}'")
    except Exception as e:
        weapon_mod_data = {}
        print(f"Failed to scan mod folders: {e}")

weapon_folder_data = {}

def on_weapons_folder_update(self, context):
    global weapon_folder_data
    path = bpy.path.abspath(self.weapons_folder)
    weapon_folder_data = {}
    try:
        for category in os.listdir(path):
            cat_path = os.path.join(path, category)
            if os.path.isdir(cat_path):
                weapon_folder_data[category] = [
                    w for w in os.listdir(cat_path)
                    if os.path.isdir(os.path.join(cat_path, w))
                ]
        print(f"Scanned weapons in '{path}'")
        build_weapon_menus()
    except Exception as e:
        print(f"Error scanning weapons: {e}")

def build_weapon_menus():
    global weapon_folder_data

    # Unregister old dynamic classes
    for cls in list(bpy.types.Menu.__subclasses__()):
        if cls.__name__.startswith("EFT_MT_weapon_category_") or cls.__name__.startswith("EFT_MT_weapon_range_"):
            try:
                bpy.utils.unregister_class(cls)
            except:
                pass

    # Group categories by letter range (A–C, D–F, etc.)
    groups = {
        "A–C": [],
        "D–F": [],
        "G–I": [],
        "J–L": [],
        "M–O": [],
        "P–R": [],
        "S–U": [],
        "V–Z": [],
        "Other": []
    }

    def get_group(letter):
        letter = letter.upper()
        for group in groups:
            if group == "Other":
                continue
            start, end = group.split("–")
            if start <= letter <= end:
                return group
        return "Other"

    for category in weapon_folder_data:
        first_char = category[0]
        group = get_group(first_char)
        groups[group].append(category)

    # Register menus for each category
    for category, weapons in weapon_folder_data.items():
        cls_name = f"EFT_MT_weapon_category_{category}"

        def make_draw_fn(category, weapons):
            def draw_fn(self, context):
                layout = self.layout
                for weapon in sorted(weapons):
                    op = layout.operator("wm.eft_select_weapon", text=weapon, icon='FILE_3D')
                    op.weapon_path = f"{category}/{weapon}"
            return draw_fn

        new_cls = type(cls_name, (bpy.types.Menu,), {
            "bl_idname": cls_name,
            "bl_label": category,
            "draw": make_draw_fn(category, weapons)
        })

        bpy.utils.register_class(new_cls)

    # Register grouped range menus (e.g., A–C)
    for group_name, categories in groups.items():
        if not categories:
            continue

        cls_name = f"EFT_MT_weapon_range_{group_name.replace('–', '_')}"

        def make_range_draw_fn(categories):
            def draw_fn(self, context):
                layout = self.layout
                for category in sorted(categories):
                    layout.menu(f"EFT_MT_weapon_category_{category}")
            return draw_fn

        new_cls = type(cls_name, (bpy.types.Menu,), {
            "bl_idname": cls_name,
            "bl_label": group_name,
            "draw": make_range_draw_fn(categories)
        })

        bpy.utils.register_class(new_cls)

def get_weapon_choices():
    global weapon_folder_data
    items = []
    for category, weapons in weapon_folder_data.items():
        for w in weapons:
            full = f"{category}/{w}"
            label = f"{w} ({category})"
            items.append((full, label, ""))
    return items or [("NONE", "None", "")]


def load_compat_data(root):
    global weapon_compat_data
    base = os.path.abspath(root)
    path = os.path.join(base, "weapon_compatibility.json")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            weapon_compat_data = json.load(f)
        print(f"Loaded compatibility data from '{path}'")
    except Exception as e:
        weapon_compat_data = {}
        print(f"Failed to load compatibility data: {e}")


def rebuild_mod_props():
    clear_mod_props()
    cats = set(weapon_mod_data.keys())
    for w in weapon_compat_data:
        cats.update(weapon_compat_data[w].keys())
    for cat in cats:
        setattr(
            bpy.types.Scene,
            f"mod_{cat}",
            bpy.props.EnumProperty(name=cat, items=build_items_cb(cat))
        )


def on_mods_folder_update(self, context):
    root = self.mods_folder
    if root and os.path.isdir(bpy.path.abspath(root)):
        load_mod_data(root)
        load_compat_data(root)
        rebuild_mod_props()
    return None


def get_bone_items(self, context):
    return bone_items_cache or [("", "No mod bones", "")]


def get_weapon_items(self, context):
    items = [("NONE", "None", "")] + [(w, w, "") for w in weapon_compat_data.keys()]
    return items or [("NONE", "None", "")]


def build_items_cb(category):
    def items(self, context):
        p = context.scene.eft_props
        filter_str = p.filter_text.lower()
        w = p.weapon_type
        if not w or w == "NONE":
            mods = weapon_mod_data.get(category, [])
        else:
            mods = weapon_compat_data.get(w, {}).get(category, [])
        # apply text filter
        if filter_str:
            mods = [m for m in mods if filter_str in m.lower()]
        return [("NONE", "None", "")] + [(m, m, "") for m in mods]
    return items


class EFTProperties(bpy.types.PropertyGroup):
    bone_list: bpy.props.EnumProperty(name="Mod Bone", items=get_bone_items)
    use_tail: bpy.props.BoolProperty(
        name="Snap to Bone-Head",
        description="Snap mod to the bone head instead of the tail",
        default=True
    )
    mods_folder: bpy.props.StringProperty(
        name="Mods Folder", subtype='DIR_PATH', update=on_mods_folder_update
    )
    weapons_folder: bpy.props.StringProperty(
        name="Weapons Folder", subtype='DIR_PATH', update=lambda s, c: on_weapons_folder_update(s, c)
    )
    weapon_choice: bpy.props.EnumProperty(
        name="Weapon to Import", items=lambda s, c: get_weapon_choices()
    )
    selected_weapon: bpy.props.StringProperty(
        name="Selected Weapon", default="NONE"
    )
    weapon_type: bpy.props.EnumProperty(name="Weapon", items=get_weapon_items)
    filter_text: bpy.props.StringProperty(
        name="Filter Mods",
        description="Filter mod dropdowns by name",
        default=""
    )

class EFT_OT_build_bones(bpy.types.Operator):
    bl_idname = "object.build_eft_bones"
    bl_label = "Build Bones from Empties"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from mathutils import Vector

        def create_bone_from_empty(empty, ebones, parent_bone=None, armature_matrix_inv=None):
            head_world = empty.matrix_world.to_translation()
            head_local = armature_matrix_inv @ head_world

            direction_world = empty.matrix_world.to_quaternion() @ Vector((0, 0.1, 0))
            tail_world = head_world + direction_world
            tail_local = armature_matrix_inv @ tail_world

            if (tail_local - head_local).length < 0.001:
                tail_local = head_local + Vector((0, 0.01, 0))

            bone = ebones.new(empty.name)
            bone.head = head_local
            bone.tail = tail_local
            if parent_bone:
                bone.parent = parent_bone
            return bone

        def convert_empty_root_to_armature(root_name):
            root_empty = bpy.data.objects.get(root_name)
            if not root_empty:
                self.report({'ERROR'}, f"Root empty '{root_name}' not found.")
                return

            root_world_matrix = root_empty.matrix_world.copy()
            empties = []

            def gather_empties(obj):
                if obj.type == 'EMPTY':
                    empties.append(obj)
                    for child in obj.children:
                        gather_empties(child)
            gather_empties(root_empty)
            empty_names = [e.name for e in empties]

            bpy.ops.object.select_all(action='DESELECT')
            bpy.ops.object.armature_add()
            armature = bpy.context.active_object
            armature.name = "Armature_" + root_empty.name
            armature.matrix_world = root_world_matrix
            armature_matrix_inv = armature.matrix_world.inverted()

            bpy.ops.object.mode_set(mode='EDIT')
            ebones = armature.data.edit_bones
            if "Bone" in ebones:
                ebones.remove(ebones["Bone"])

            def add_bones_recursive(empty_obj, parent_bone=None):
                bone = create_bone_from_empty(empty_obj, ebones, parent_bone, armature_matrix_inv)
                for child in empty_obj.children:
                    if child.type == 'EMPTY':
                        add_bones_recursive(child, bone)

            add_bones_recursive(root_empty)
            bpy.ops.object.mode_set(mode='OBJECT')

            lod1_meshes = [obj for obj in bpy.data.objects if obj.type == 'MESH' and obj.name.endswith('_LOD1')]
            for obj in lod1_meshes:
                bpy.data.objects.remove(obj, do_unlink=True)

            mesh_objs = []
            for obj in bpy.data.objects:
                if obj.type == 'MESH' and obj.parent and obj.parent.name in empty_names:
                    mesh_objs.append(obj)
                    matrix = obj.matrix_world.copy()
                    obj.parent = armature
                    obj.matrix_world = matrix

            bpy.ops.object.select_all(action='DESELECT')
            for obj in mesh_objs:
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                obj.select_set(False)

            for name in empty_names:
                obj = bpy.data.objects.get(name)
                if obj:
                    bpy.data.objects.remove(obj, do_unlink=True)

            print(f"✅ Done: {root_name}")

        selected_root_names = [
            obj.name for obj in bpy.context.selected_objects
            if obj.type == 'EMPTY' and not obj.parent
        ]

        if not selected_root_names:
            self.report({'WARNING'}, "No root empties selected.")
            return {'CANCELLED'}

        for name in selected_root_names:
            convert_empty_root_to_armature(name)

        self.report({'INFO'}, f"Built bones for: {', '.join(selected_root_names)}")
        return {'FINISHED'}


class EFT_OT_refresh_bone_list(bpy.types.Operator):
    bl_idname = "object.refresh_bone_list"
    bl_label = "Refresh Mod Bone List"

    def execute(self, context):
        global bone_items_cache
        bone_items_cache = []

        root_armature = next((o for o in context.selected_objects if o.type == 'ARMATURE'), None)
        if not root_armature:
            self.report({'ERROR'}, "No armature selected")
            return {'CANCELLED'}

        def collect_mod_bones_recursively(arm_obj):
            items = []
            if arm_obj.type != 'ARMATURE':
                return items
            for b in arm_obj.data.bones:
                if b.name.startswith("mod_"):
                    clean_name = arm_obj.name.removeprefix("Armature_")
                    label = f"{b.name} ({clean_name})"
                    items.append((f"{arm_obj.name}::{b.name}", label, ""))
            for child in arm_obj.children:
                items.extend(collect_mod_bones_recursively(child))
            return items

        bone_items_cache = collect_mod_bones_recursively(root_armature)
        self.report({'INFO'}, f"Found {len(bone_items_cache)} mod bones")
        return {'FINISHED'}


class EFT_OT_set_bone_display_stick(bpy.types.Operator):
    bl_idname = "object.set_bone_display_stick"
    bl_label = "Set Bone Display to Stick"
    bl_description = "Set all armatures' bone display style to Stick"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                obj.data.display_type = 'STICK'
        self.report({'INFO'}, "Set all armatures to Stick display")
        return {'FINISHED'}



class EFT_OT_attach_mod(bpy.types.Operator):
    bl_idname = "object.attach_eft_mod"
    bl_label = "Attach EFT Mod"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        props = context.scene.eft_props
        selected_armatures = [o for o in context.selected_objects if o.type == 'ARMATURE']
        if len(selected_armatures) < 2:
            self.report({'ERROR'}, "Select weapon and mod armatures")
            return {'CANCELLED'}

        weapon_root = selected_armatures[0]
        mod = selected_armatures[1]

        try:
            armature_name, bone_name = props.bone_list.split("::", 1)
        except ValueError:
            self.report({'ERROR'}, "Bone data is malformed")
            return {'CANCELLED'}

        target_arm = bpy.data.objects.get(armature_name)
        if not target_arm or target_arm.type != 'ARMATURE':
            self.report({'ERROR'}, f"Target armature '{armature_name}' not found")
            return {'CANCELLED'}

        bone = target_arm.data.bones.get(bone_name)
        pose = target_arm.pose.bones.get(bone_name)

        if not bone or not pose:
            self.report({'ERROR'}, f"Bone '{bone_name}' not found in '{armature_name}'")
            return {'CANCELLED'}

        pt = bone.tail_local if props.use_tail else bone.head_local
        world = target_arm.matrix_world @ pt

        mod.parent = target_arm
        mod.parent_type = 'BONE'
        mod.parent_bone = bone_name
        mod.matrix_parent_inverse.identity()

        mw = target_arm.matrix_world @ pose.matrix
        loc = mw.inverted() @ world
        if props.use_tail:
            loc.y *= -1
        mod.location = loc

        return {'FINISHED'}

class EFT_OT_open_weapon_browser(bpy.types.Operator):
    bl_idname = "wm.eft_weapon_browser"
    bl_label = "Browse Weapons"

    def execute(self, context):
        bpy.ops.wm.call_menu(name="EFT_MT_weapon_menu")
        return {'FINISHED'}


class EFT_MT_weapon_menu(bpy.types.Menu):
    bl_label = "Weapons"

    def draw(self, context):
        layout = self.layout
        for label in ["A–C", "D–F", "G–I", "J–L", "M–O", "P–R", "S–U", "V–Z", "Other"]:
            layout.menu(f"EFT_MT_weapon_range_{label.replace('–', '_')}")



class EFT_OT_select_weapon(bpy.types.Operator):
    bl_idname = "wm.eft_select_weapon"
    bl_label = "Select Weapon"

    weapon_path: bpy.props.StringProperty()

    def execute(self, context):
        context.scene.eft_props.selected_weapon = self.weapon_path
        self.report({'INFO'}, f"Selected: {self.weapon_path}")
        return {'FINISHED'}


class EFT_OT_import_selected_weapon(bpy.types.Operator):
    bl_idname = "object.import_selected_weapon"
    bl_label = "Import Selected Weapon"

    def execute(self, context):
        p = context.scene.eft_props
        if not p.weapons_folder or p.selected_weapon == "NONE":
            self.report({'ERROR'}, "No weapon selected")
            return {'CANCELLED'}

        root = bpy.path.abspath(p.weapons_folder)
        category, weapon = p.selected_weapon.split("/", 1)
        fbx_path = os.path.join(root, category, weapon, f"{weapon}.fbx")

        if not os.path.exists(fbx_path):
            self.report({'ERROR'}, f"FBX not found at:\n{fbx_path}")
            return {'CANCELLED'}

        bpy.ops.import_scene.fbx(filepath=fbx_path)
        self.report({'INFO'}, f"Imported: {weapon}")
        return {'FINISHED'}


class EFT_OT_import_mods(bpy.types.Operator):
    bl_idname = "object.import_all_mods"
    bl_label = "Import Selected Mods"
    def execute(self, context):
        sc = context.scene; p = sc.eft_props
        root = bpy.path.abspath(p.mods_folder)
        categories = (
            weapon_compat_data.get(p.weapon_type, {})
            if p.weapon_type and p.weapon_type != 'NONE'
            else weapon_mod_data
        )
        for cat in categories:
            sel = getattr(sc, f"mod_{cat}", "NONE")
            if sel not in (None, 'NONE'):
                fbx = os.path.join(root, cat, sel, f"{sel}.fbx")
                if os.path.exists(fbx):
                    bpy.ops.import_scene.fbx(filepath=fbx)
                else:
                    self.report({'WARNING'}, f"Missing {fbx}")
        return {'FINISHED'}

class EFT_OT_reset_mod_selection(bpy.types.Operator):
    bl_idname = "object.reset_mod_selection"
    bl_label = "Reset Mod Selection"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        sc = context.scene
        p = sc.eft_props
        categories = (
            weapon_compat_data.get(p.weapon_type, {})
            if p.weapon_type and p.weapon_type != 'NONE'
            else weapon_mod_data
        )
        for cat in categories:
            prop_name = f"mod_{cat}"
            if hasattr(sc, prop_name):
                setattr(sc, prop_name, 'NONE')
        self.report({'INFO'}, "Mod selections reset to None")
        return {'FINISHED'}

def find_texture_folder_for(obj, context):
    props = context.scene.eft_props
    mods_path = bpy.path.abspath(props.mods_folder)
    weapons_path = bpy.path.abspath(props.weapons_folder)
    selected_weapon = props.selected_weapon

    # 1. Try matching from mod parent armature
    if obj.parent and obj.parent.type == 'ARMATURE':
        parent_name = obj.parent.name.lower()
        if not ("weapon_" in parent_name or "armature_weapon" in parent_name):
            mod_folder = parent_name.replace("armature_", "")
            mod_path = os.path.join(mods_path, mod_folder)
            # Search all subfolders in mods_path for a match
            for category in os.listdir(mods_path):
                category_path = os.path.join(mods_path, category)
                if not os.path.isdir(category_path):
                    continue

                candidate_path = os.path.join(category_path, mod_folder)
                if os.path.isdir(candidate_path):
                    print(f"[AutoTexture] {obj.name} → using mod folder: {candidate_path}")
                    return candidate_path

            # If we reach this point, it wasn't found
            print(f"[AutoTexture] {obj.name} → mod folder not found in any category: {mod_folder}")




    # 2. Fallback to weapon_mod_data mesh name matching (original working method)
    if hasattr(context.scene, "eft_props") and hasattr(context.scene.eft_props, "mods_folder"):
        base = obj.name.rsplit("_LOD0", 1)[0].lower()
        for category, mods in weapon_mod_data.items():
            for mod in mods:
                if mod.lower() in base:
                    mod_path = os.path.join(mods_path, category, mod)
                    if os.path.isdir(mod_path):
                        print(f"[AutoTexture] {obj.name} → using fallback mod folder: {mod_path}")
                        return mod_path

    # 3. Try selected weapon fallback
    if selected_weapon != "NONE":
        try:
            category, weapon = selected_weapon.split("/", 1)
            weapon_path = os.path.join(weapons_path, category, weapon)
            if os.path.isdir(weapon_path):
                print(f"[AutoTexture] {obj.name} → using weapon folder: {weapon_path}")
                return weapon_path
        except:
            pass

    return None




class EFT_OT_auto_texture(bpy.types.Operator):
    bl_idname = "object.auto_texture"
    bl_label = "Auto Texture (EFT Shader)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        p = context.scene.eft_props
        mods_root = bpy.path.abspath(p.mods_folder)
        shader_group = bpy.data.node_groups.get("EFT Shader v1")

        if not shader_group:
            self.report({'ERROR'}, "EFT Shader v1 node group not found.")
            return {'CANCELLED'}

        for obj in context.selected_objects:
            if obj.type != 'MESH' or "_LOD0" not in obj.name:
                continue

            tex_folder = find_texture_folder_for(obj, context)
            if not tex_folder:
                self.report({'WARNING'}, f"No texture folder found for {obj.name}")
                continue

            files = os.listdir(tex_folder)
            base_name = obj.name.rsplit("_LOD0", 1)[0].lower()

            def find_texture(obj_name, files, type_keywords):
                # Normalize name (remove .001, .002)
                clean_name = re.sub(r'\.\d{3}$', '', obj_name.lower())

                # Match base ending with _lod0
                match = re.match(r"(.*_lod0)", clean_name)
                if not match:
                    return None
                expected_base = match.group(1)

                def is_valid(f):
                    name_no_ext = os.path.splitext(f)[0].lower()
                    return (
                        "lod1" not in name_no_ext and
                        name_no_ext.startswith(expected_base) and
                        any(k in name_no_ext for k in type_keywords)
                    )

                exact_matches = [f for f in files if is_valid(f)]
                if exact_matches:
                    return exact_matches[0]

                # --- Fallback: choose closest matching texture ---
                def score(f):
                    name_no_ext = os.path.splitext(f)[0].lower()
                    if "lod1" in name_no_ext:
                        return -1
                    if not any(k in name_no_ext for k in type_keywords):
                        return -1
                    return len(os.path.commonprefix([expected_base, name_no_ext]))

                fallback_matches = sorted(files, key=score, reverse=True)
                best = fallback_matches[0] if fallback_matches and score(fallback_matches[0]) > 0 else None

                if best:
                    print(f"[Fallback Texture] {obj_name} → {best}")

                return best


            diff  = find_texture(obj.name, files, ["_diff"])
            gloss = find_texture(obj.name, files, ["_gloss", "_glos", "_spec"])
            norm  = find_texture(obj.name, files, ["_nrm", "_normal"])


            mat = obj.active_material or bpy.data.materials.new(name=f"{obj.name}_Mat")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()

            out = nodes.new("ShaderNodeGroup")
            out.node_tree = shader_group

            def load_tex(fn, label, cs, in_c, in_a=None):
                path = os.path.join(tex_folder, fn) if fn else None
                if path and os.path.exists(path):
                    tn = nodes.new("ShaderNodeTexImage")
                    tn.label = label
                    tn.image = bpy.data.images.load(path)
                    tn.image.colorspace_settings.name = cs
                    links.new(tn.outputs['Color'], out.inputs[in_c])
                    if in_a:
                        links.new(tn.outputs['Alpha'], out.inputs[in_a])

            load_tex(diff,  "Diffuse",   'sRGB',      'Diffuse Color',  'Diffuse Alpha')
            load_tex(gloss, "Glossiness",'sRGB',      'Glossiness Color','Glossiness Alpha')

            if norm:
                tn = nodes.new("ShaderNodeTexImage")
                tn.label = "Normal"
                tn.image = bpy.data.images.load(os.path.join(tex_folder, norm))
                tn.image.colorspace_settings.name = 'Non-Color'
                links.new(tn.outputs['Color'], out.inputs['Red Normal Color'])

            out_node = nodes.new("ShaderNodeOutputMaterial")
            links.new(out.outputs['BSDF'], out_node.inputs['Surface'])
            obj.active_material = mat

        return {'FINISHED'}




class EFT_OT_auto_texture_principled(bpy.types.Operator):
    bl_idname = "object.auto_texture_principled"
    bl_label = "Auto Texture (Principled)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type != 'MESH' or "_LOD0" not in obj.name:
                continue

            tex_folder = find_texture_folder_for(obj, context)
            if not tex_folder:
                self.report({'WARNING'}, f"No texture folder found for {obj.name}")
                continue

            files = os.listdir(tex_folder)
            base_name = obj.name.rsplit("_LOD0", 1)[0].lower()

            def find_texture(obj_name, files, type_keywords):
                # Normalize name (remove .001, .002)
                clean_name = re.sub(r'\.\d{3}$', '', obj_name.lower())

                # Match base ending with _lod0
                match = re.match(r"(.*_lod0)", clean_name)
                if not match:
                    return None
                expected_base = match.group(1)

                def is_valid(f):
                    name_no_ext = os.path.splitext(f)[0].lower()
                    return (
                        "lod1" not in name_no_ext and
                        name_no_ext.startswith(expected_base) and
                        any(k in name_no_ext for k in type_keywords)
                    )

                exact_matches = [f for f in files if is_valid(f)]
                if exact_matches:
                    return exact_matches[0]

                # --- Fallback: choose closest matching texture ---
                def score(f):
                    name_no_ext = os.path.splitext(f)[0].lower()
                    if "lod1" in name_no_ext:
                        return -1
                    if not any(k in name_no_ext for k in type_keywords):
                        return -1
                    return len(os.path.commonprefix([expected_base, name_no_ext]))

                fallback_matches = sorted(files, key=score, reverse=True)
                best = fallback_matches[0] if fallback_matches and score(fallback_matches[0]) > 0 else None

                if best:
                    print(f"[Fallback Texture] {obj_name} → {best}")

                return best

            diff  = find_texture(obj.name, files, ["_diff"])
            gloss = find_texture(obj.name, files, ["_gloss", "_glos", "_spec"])
            norm  = find_texture(obj.name, files, ["_nrm", "_normal"])

            mat = obj.active_material or bpy.data.materials.new(name=f"{obj.name}_Mat")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()

            output = nodes.new("ShaderNodeOutputMaterial")
            principled = nodes.new("ShaderNodeBsdfPrincipled")
            principled.location = (300, 0)
            principled.inputs['IOR'].default_value = 1.45

            invert = nodes.new("ShaderNodeInvert")
            invert.location = (0, -150)
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (0, -300)

            links.new(principled.outputs["BSDF"], output.inputs["Surface"])

            def load_tex(fn, label, cs):
                if not fn:
                    return None
                path = os.path.join(tex_folder, fn)
                if os.path.exists(path):
                    tex = nodes.new("ShaderNodeTexImage")
                    tex.label = label
                    tex.image = bpy.data.images.load(path)
                    tex.image.colorspace_settings.name = cs
                    return tex
                return None

            tex_diff = load_tex(diff, "Base Color", "sRGB")
            tex_gloss = load_tex(gloss, "Gloss", "sRGB")
            tex_norm = load_tex(norm, "Normal", "Non-Color")

            if tex_diff:
                links.new(tex_diff.outputs["Color"], principled.inputs["Base Color"])
                if "Alpha" in tex_diff.outputs:
                    links.new(tex_diff.outputs["Alpha"], principled.inputs["Specular IOR Level"])

            if tex_gloss:
                links.new(tex_gloss.outputs["Color"], invert.inputs["Color"])
                links.new(invert.outputs["Color"], principled.inputs["Roughness"])
                if "Alpha" in tex_gloss.outputs:
                    links.new(tex_gloss.outputs["Alpha"], principled.inputs["Alpha"])

            if tex_norm:
                links.new(tex_norm.outputs["Color"], normal_map.inputs["Color"])
                links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

            obj.active_material = mat

        return {'FINISHED'}



class EFT_OT_auto_bake_gloss(bpy.types.Operator):
    bl_idname = "object.auto_bake_gloss"
    bl_label = "Auto‑Bake Gloss → Roughness"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import os

        def srgb_to_linear(c):
            if c <= 0.04045:
                return c / 12.92
            else:
                return ((c + 0.055) / 1.055) ** 2.4

        for obj in context.selected_objects:
            if obj.type != 'MESH' or "_LOD0" not in obj.name:
                continue
            bpy.context.view_layer.objects.active = obj

            for slot in obj.material_slots:
                mat = slot.material
                if not mat or not mat.use_nodes:
                    continue
                nt = mat.node_tree

                # Find the invert node that’s fed by gloss image
                inv_link = next((
                    l for l in nt.links
                    if isinstance(l.to_node, bpy.types.ShaderNodeInvert)
                    and l.to_socket.name == "Color"
                ), None)

                if not inv_link:
                    continue

                gloss_node = inv_link.from_node
                gloss_img = gloss_node.image
                if not gloss_img:
                    continue

                # Derive the output folder from the gloss image path
                gloss_path = bpy.path.abspath(gloss_img.filepath_raw)
                gloss_dir = os.path.dirname(gloss_path)
                gloss_basename = os.path.splitext(os.path.basename(gloss_path))[0]

                # Build the output path
                baked_name = f"{gloss_basename}_rough.png"
                dst = os.path.join(gloss_dir, baked_name)

                if os.path.exists(dst):
                    print(f"[EFT Bake] {baked_name} already exists, skipping.")
                    continue

                # Copy the image to start
                rough = gloss_img.copy()
                rough.colorspace_settings.name = 'Non-Color'

                orig = list(gloss_img.pixels)
                outp = []

                for i in range(0, len(orig), 4):
                    sr = orig[i]
                    lr = srgb_to_linear(sr)
                    inv = 1.0 - lr
                    outp.extend([inv, inv, inv, orig[i+3]])

                rough.pixels[:] = outp
                rough.filepath_raw = dst
                rough.file_format = 'PNG'
                rough.save()

                print(f"[EFT Bake] wrote → {dst}")
                # Hook into Principled.Roughness
                pbsdf = next((
                    n for n in nt.nodes
                    if isinstance(n, bpy.types.ShaderNodeBsdfPrincipled)
                ), None)

                if pbsdf:
                    tex = nt.nodes.new('ShaderNodeTexImage')
                    tex.image = rough
                    tex.image.colorspace_settings.name = 'Non-Color'
                    nt.links.new(tex.outputs['Color'], pbsdf.inputs['Roughness'])

                # Clean up old gloss + invert nodes
                nt.nodes.remove(gloss_node)
                nt.nodes.remove(inv_link.to_node)



        self.report({'INFO'}, f"Baked roughness maps next to original gloss maps.")
        return {'FINISHED'}




class EFT_PT_panel(bpy.types.Panel):
    bl_label = "EFT Weapon Builder"
    bl_idname = "EFT_PT_weapon_mod_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'EFT Mod Tool'

    def draw(self, context):
        l = self.layout
        p = context.scene.eft_props

        l.operator("object.refresh_bone_list")
        l.prop(p, "bone_list")
        row = l.row(align=True)
        row.prop(p, "use_tail")
        row.operator("object.set_bone_display_stick", text="", icon='ARMATURE_DATA')
        l.operator("object.attach_eft_mod")

        l.separator()
        row = l.row(align=True)
        row.label(text=f"Weapon: {p.selected_weapon if p.selected_weapon != 'NONE' else 'None'}")
        row.operator("wm.eft_weapon_browser", text="", icon='FILE_FOLDER')
        l.operator("object.import_selected_weapon", text="Import Selected Weapon")
        l.prop(p, "weapons_folder")
        l.prop(p, "mods_folder")
        l.prop(p, "weapon_type")
        l.prop(p, "filter_text")

        cats = (
            weapon_compat_data.get(p.weapon_type, {})
            if p.weapon_type and p.weapon_type != 'NONE'
            else weapon_mod_data
        )
        for cat in cats:
            prop = f"mod_{cat}"
            if hasattr(context.scene, prop):
                l.prop(context.scene, prop)

        l.operator("object.import_all_mods")
        l.operator("object.reset_mod_selection", text="Reset Mod Selection")
        l.separator()
        l.operator("object.build_eft_bones", text="Build Bones from Empties")
        l.operator("object.auto_texture", text="Auto Texture (EFT Shader)")
        l.operator("object.auto_texture_principled", text="Auto Texture (Principled)")
        l.operator("object.auto_bake_gloss", text="Auto‑Bake Gloss→Roughness")


classes = (
    EFTProperties,
    EFT_OT_build_bones,
    EFT_OT_refresh_bone_list,
    EFT_OT_open_weapon_browser,
    EFT_MT_weapon_menu,
    EFT_OT_select_weapon,
    EFT_OT_attach_mod,
    EFT_OT_import_selected_weapon,
    EFT_OT_import_mods,
    EFT_OT_auto_texture,
    EFT_OT_auto_texture_principled,
    EFT_OT_auto_bake_gloss,
    EFT_OT_reset_mod_selection,
    EFT_OT_set_bone_display_stick,
    EFT_PT_panel,
)


def register():
    clear_mod_props()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.eft_props = bpy.props.PointerProperty(type=EFTProperties)

    # Delay shader load to avoid _RestrictData error
    bpy.app.timers.register(ensure_eft_shader_loaded, first_interval=0.5)

    # Also re-load it after opening .blend files
    if ensure_eft_shader_loaded not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(ensure_eft_shader_loaded)



def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    clear_mod_props()
    del bpy.types.Scene.eft_props


if __name__ == "__main__":
    register()
